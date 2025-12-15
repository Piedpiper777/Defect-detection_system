import os
import logging
from typing import Dict, Any, List, Optional, Tuple
from .kg_service import neo4j_service
from .vector_store import search_enhanced, index_exists
from .llm_service import llm_generate_cypher
from .schema_store import load_schema

logger = logging.getLogger(__name__)


class RAGService:
    """统一的RAG服务，整合知识图谱和向量数据库检索"""

    def __init__(self):
        self.schema = None
        self._load_schema()

    def _load_schema(self):
        """加载知识图谱schema"""
        try:
            self.schema = load_schema()
        except Exception as e:
            logger.warning(f"Failed to load schema: {e}")
            self.schema = None

    def _analyze_query_type(self, question: str) -> Dict[str, Any]:
        """分析查询类型和关键词"""
        question_lower = question.lower()

        # 检测问题类型
        query_type = {
            'is_defect_query': any(word in question_lower for word in ['缺陷', '问题', '故障', '异常']),
            'is_cause_query': any(word in question_lower for word in ['原因', '为什么', '怎么回事']),
            'is_solution_query': any(word in question_lower for word in ['解决', '怎么办', '如何', '方法']),
            'is_general_query': any(word in question_lower for word in ['介绍', '概述', '类型', '分类'])
        }

        # 提取关键词
        defect_keywords = [
            '划痕', '开路', '短路', '鼠咬', '针孔', '钻孔错位', '铜不足', '过刻蚀', '欠刻蚀',
            '焊桥', '焊锡不足', '焊锡过多', '通孔空洞', '分层', '表面污染', '纤维暴露',
            '焊盘翘起', '起泡', '毛刺', '裂纹'
        ]

        found_keywords = [kw for kw in defect_keywords if kw in question]

        return {
            'query_type': query_type,
            'keywords': found_keywords,
            'has_specific_defect': len(found_keywords) > 0
        }

    def _search_knowledge_graph(self, question: str, query_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """从知识图谱中检索相关信息"""
        try:
            # 生成Cypher查询
            gen_result = llm_generate_cypher(question, max_retries=2, max_limit=50)
            if not gen_result.get('success'):
                return {'success': False, 'error': gen_result.get('error'), 'results': []}

            cypher = gen_result.get('normalized', '')
            if not cypher:
                return {'success': False, 'error': 'Generated empty Cypher', 'results': []}

            # 执行查询
            exec_result = neo4j_service.execute_readonly_query(cypher, max_rows=50)
            if not exec_result.get('success'):
                return {'success': False, 'error': exec_result.get('error'), 'results': []}

            results = exec_result.get('results', [])
            count = exec_result.get('count', 0)

            # 格式化结果
            formatted_results = []
            for result in results[:10]:  # 限制返回前10个结果
                formatted_results.append({
                    'type': 'graph_data',
                    'content': str(result),
                    'source': 'knowledge_graph',
                    'relevance_score': 0.8  # 知识图谱结果给予较高基础权重
                })

            return {
                'success': True,
                'results': formatted_results,
                'cypher': cypher,
                'count': count
            }

        except Exception as e:
            logger.error(f"Knowledge graph search failed: {e}")
            return {'success': False, 'error': str(e), 'results': []}

    def _search_vector_db(self, question: str, query_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """从向量数据库中检索相关信息"""
        try:
            if not index_exists():
                logger.warning("Vector index not found")
                return {'success': False, 'error': 'Vector index not found', 'results': []}

            # 根据查询类型调整检索参数
            k = 8 if query_analysis.get('query_type', {}).get('is_general_query') else 5
            if query_analysis.get('has_specific_defect'):
                k = 3  # 针对特定缺陷的问题，减少检索数量

            # 获取模型路径，支持环境变量和默认路径
            model_path = os.getenv('SENT_MODEL_PATH')
            if not model_path:
                # 默认模型路径
                model_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'models', 'Jerry0', 'text2vec-base-chinese')

            search_result = search_enhanced(question, k=k, model_path=model_path)

            if not search_result.get('success'):
                logger.warning(f"Vector search failed: {search_result.get('error')}")
                return {'success': False, 'error': search_result.get('error'), 'results': []}

            # 格式化结果
            formatted_results = []
            for result in search_result.get('results', []):
                item = result.get('item', {})
                score = result.get('score', 0.0)

                formatted_results.append({
                    'type': 'text_document',
                    'id': item.get('id'),
                    'content': item.get('text', ''),
                    'source': 'vector_db',
                    'relevance_score': score
                })

            return {
                'success': True,
                'results': formatted_results,
                'stats': search_result.get('stats', {})
            }

        except Exception as e:
            logger.error(f"Vector DB search failed: {e}")
            return {'success': False, 'error': str(e), 'results': []}

    def _fuse_results(self, kg_results: List[Dict], vector_results: List[Dict],
                     query_analysis: Dict[str, Any]) -> List[Dict]:
        """融合知识图谱和向量数据库的检索结果"""

        all_results = []

        # 添加知识图谱结果
        for result in kg_results:
            # 根据查询类型调整权重
            if query_analysis.get('query_type', {}).get('is_general_query'):
                result['final_score'] = result['relevance_score'] * 1.2  # 通用问题偏好图谱数据
            else:
                result['final_score'] = result['relevance_score'] * 1.0
            all_results.append(result)

        # 添加向量数据库结果
        for result in vector_results:
            base_score = result['relevance_score']

            # 根据查询类型和内容调整权重
            if query_analysis.get('query_type', {}).get('is_solution_query'):
                # 解决方案类问题偏好向量数据库
                base_score *= 1.3
            elif query_analysis.get('query_type', {}).get('is_defect_query'):
                base_score *= 1.2

            # 如果包含关键词，进一步提升权重
            if query_analysis.get('keywords') and any(kw in result['content'] for kw in query_analysis['keywords']):
                base_score *= 1.4

            result['final_score'] = base_score
            all_results.append(result)

        # 按最终得分排序
        all_results.sort(key=lambda x: x['final_score'], reverse=True)

        # 多样性筛选：确保不同类型的结果都有代表
        final_results = []
        graph_count = 0
        vector_count = 0
        max_per_type = 5

        for result in all_results:
            if result['source'] == 'knowledge_graph' and graph_count < max_per_type:
                final_results.append(result)
                graph_count += 1
            elif result['source'] == 'vector_db' and vector_count < max_per_type:
                final_results.append(result)
                vector_count += 1

            if graph_count >= max_per_type and vector_count >= max_per_type:
                break

        return final_results

    def format_results_for_llm(self, results: List[Dict[str, Any]]) -> str:
        """将检索结果格式化为LLM友好的文本"""
        if not results:
            return ""

        formatted_parts = []
        for i, result in enumerate(results, 1):
            content = result.get('content', '').strip()
            score = result.get('final_score', 0)
            source = result.get('source', 'unknown')

            if result.get('type') == 'text_document':
                doc_id = result.get('id', 'unknown')
                formatted_parts.append(f"[文档 {doc_id}] {content}")
            elif result.get('type') == 'graph_data':
                formatted_parts.append(f"[图谱数据] {content}")

        return "\n\n".join(formatted_parts)

    def retrieve_for_llm(self, question: str, max_results: int = 10) -> Dict[str, Any]:
        """专为LLM优化的检索接口"""
        base_result = self.retrieve(question)

        if not base_result.get('success'):
            return base_result

        # 限制结果数量
        results = base_result['results'][:max_results]

        # 格式化为LLM友好的文本
        formatted_text = self.format_results_for_llm(results)

        return {
            'success': True,
            'formatted_text': formatted_text,
            'results': results,
            'query_analysis': base_result.get('query_analysis'),
            'stats': base_result.get('stats')
        }

    def retrieve(self, question: str) -> Dict[str, Any]:
        """统一的检索接口，同时从知识图谱和向量数据库检索信息"""

        if not question or not question.strip():
            return {'success': False, 'error': 'Question cannot be empty', 'results': []}

        # 分析查询
        query_analysis = self._analyze_query_type(question)
        logger.info(f"Query analysis: {query_analysis}")

        # 并行检索两个数据源
        kg_result = self._search_knowledge_graph(question, query_analysis)
        vector_result = self._search_vector_db(question, query_analysis)

        # 融合结果
        kg_results = kg_result.get('results', []) if kg_result.get('success') else []
        vector_results = vector_result.get('results', []) if vector_result.get('success') else []

        fused_results = self._fuse_results(kg_results, vector_results, query_analysis)

        # 准备返回结果
        response = {
            'success': True,
            'results': fused_results,
            'query_analysis': query_analysis,
            'stats': {
                'total_results': len(fused_results),
                'kg_results_count': len(kg_results),
                'vector_results_count': len(vector_results),
                'kg_success': kg_result.get('success', False),
                'vector_success': vector_result.get('success', False)
            }
        }

        # 如果两个数据源都失败了，返回错误；但如果至少一个成功，仍然返回结果
        if not kg_result.get('success') and not vector_result.get('success'):
            response['success'] = False
            response['error'] = f"KG: {kg_result.get('error', 'Unknown')}, Vector: {vector_result.get('error', 'Unknown')}"
        elif len(fused_results) == 0:
            # 有数据源成功但没有结果
            response['success'] = False
            response['error'] = 'No relevant results found'
        else:
            # 如果有结果，即使向量搜索失败也算成功
            response['success'] = True
            response['error'] = None

        return response


# 全局RAG服务实例
rag_service = RAGService()
