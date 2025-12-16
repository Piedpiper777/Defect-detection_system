from flask import request, jsonify
from .blueprint import llm_bp
from services.llmkg.llm_service import (
    llm_answer_stream_with_db,
    llm_generate_cypher,
    llm_generate_viz_cypher,
    build_viz_cypher_from_base,
)
from services.llmkg.kg_service import neo4j_service
import base64


@llm_bp.route('/gen_cypher', methods=['POST'])
def gen_cypher_endpoint():
    """Generate a read-only cypher from a question and return a viz-friendly cypher if possible."""
    data = request.get_json(silent=True) or {}
    question = (data.get('question') or '').strip()
    max_rows = int(data.get('max_rows', 200))
    if not question:
        return jsonify({'success': False, 'error': 'question is required'}), 400

    try:
        gen = llm_generate_cypher(question, max_retries=2, max_limit=max_rows)
        if not gen.get('success'):
            return jsonify({'success': False, 'error': gen.get('error')}), 200
        normalized = gen.get('normalized') or gen.get('cypher')
        # try to generate viz-friendly cypher
        viz_gen = llm_generate_viz_cypher(question, normalized, max_retries=1, max_limit=max_rows)
        viz = None
        if viz_gen.get('success'):
            viz = viz_gen.get('normalized') or viz_gen.get('cypher')
        else:
            viz = build_viz_cypher_from_base(normalized, default_limit=max_rows)

        return jsonify({'success': True, 'cypher': normalized, 'viz': viz}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
from flask import Response, stream_with_context

@llm_bp.route('/llm_answer', methods=['POST'])
def llm_answer_endpoint():
    """Streamed: execute DB then stream LLM answer (chunked plain text)"""
    data = request.get_json() or {}
    question = (data.get('question') or '').strip()
    max_rows = int(data.get('max_rows', 200))
    messages = data.get('messages', [])  # 接收对话历史

    if not question:
        return jsonify({'success': False, 'error': '问题不能为空'}), 400
    test_mode = bool(data.get('test_mode', False))

    # Pre-generate cypher and possible viz header so frontend can update graph immediately
    viz_cypher = None
    try:
        if not test_mode:
            gen = llm_generate_cypher(question, max_retries=2, max_limit=max_rows)
            if gen.get('success'):
                normalized = gen.get('normalized') or gen.get('cypher')
                exec_res = neo4j_service.execute_readonly_query(normalized, params=None, max_rows=max_rows)
                has_rows = exec_res.get('success') and exec_res.get('count', 0) > 0
                if has_rows:
                    viz_gen = llm_generate_viz_cypher(question, normalized, max_retries=1, max_limit=max_rows)
                    if viz_gen.get('success'):
                        viz_cypher = viz_gen.get('normalized') or viz_gen.get('cypher') or normalized
                    else:
                        viz_cypher = build_viz_cypher_from_base(normalized, default_limit=max_rows)

    except Exception:
        viz_cypher = None

    def generate():
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            logger.info(f"[API] 开始生成流式响应，问题: {question[:50]}...")
            logger.info(f"[API] messages数量: {len(messages) if messages else 0}")
            
            if test_mode:
                # Simulated end-to-end flow for testing without external LLM/Neo4j
                logger.info("[API] 使用测试模式")
                yield '[TEST MODE] Generating Cypher...\n'
                cypher = 'MATCH (n:Person) RETURN n LIMIT 10'
                yield f'[TEST MODE] Cypher: {cypher}\n'
                yield '[TEST MODE] Executing Cypher...\n'
                # construct a fake sample result
                sample = [{'n': {'type': 'node', 'id': 1, 'labels': ['Person'], 'properties': {'name': 'Alice', 'age': 30}}}]
                yield '[TEST MODE] Query returned 1 row. Streaming answer...\n'
                # stream a pretend LLM response in chunks
                answer = '数据库中有 1 个 Person：Alice（age 30）。'
                for i in range(0, len(answer), 10):
                    yield answer[i:i+10]
                logger.info("[API] 测试模式响应完成")
            else:
                chunk_count = 0
                total_length = 0
                try:
                    for chunk in llm_answer_stream_with_db(question, max_rows=max_rows, messages=messages):
                        chunk_count += 1
                        total_length += len(chunk) if chunk else 0
                        try:
                            yield chunk
                            if chunk_count % 10 == 0:
                                logger.debug(f"[API] 已发送 {chunk_count} 个chunk，总长度: {total_length}")
                        except GeneratorExit:
                            logger.warning("[API] 生成器被中断 (GeneratorExit)")
                            break
                        except Exception as yield_err:
                            logger.error(f"[API] yield chunk时出错: {yield_err}")
                            yield f"[ERROR] 流式输出错误: {str(yield_err)}"
                            break
                    
                    logger.info(f"[API] 流式响应完成，共发送 {chunk_count} 个chunk，总长度: {total_length}")
                except Exception as stream_err:
                    logger.error(f"[API] llm_answer_stream_with_db 异常: {stream_err}", exc_info=True)
                    yield f"[ERROR] 流式生成失败: {str(stream_err)}"
        except Exception as gen_err:
            logger.error(f"[API] generate函数异常: {gen_err}", exc_info=True)
            yield f"[ERROR] 生成响应失败: {str(gen_err)}"

    resp = Response(stream_with_context(generate()), mimetype='text/plain; charset=utf-8')
    # send viz cypher header if available
    if viz_cypher:
        try:
            b64 = base64.b64encode((viz_cypher or '').encode('utf-8')).decode('ascii')
            resp.headers['X-Cypher-B64'] = b64
        except Exception:
            pass
    return resp


@llm_bp.route('/sessions', methods=['GET'])
def list_sessions_endpoint():
    """获取所有会话列表"""
    try:
        from services.llmkg.session_service import list_sessions
        sessions = list_sessions()
        return jsonify({'success': True, 'sessions': sessions})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@llm_bp.route('/sessions', methods=['POST'])
def create_session_endpoint():
    """创建新会话"""
    try:
        from services.llmkg.session_service import create_session
        data = request.get_json() or {}
        session_id = data.get('id')
        title = data.get('title')
        session = create_session(session_id=session_id, title=title)
        return jsonify({'success': True, 'session': session})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@llm_bp.route('/sessions/<session_id>', methods=['GET'])
def get_session_endpoint(session_id):
    """获取会话信息和消息"""
    try:
        from services.llmkg.session_service import get_session_info, load_session_messages
        info = get_session_info(session_id)
        if not info:
            return jsonify({'success': False, 'error': '会话不存在'}), 404
        messages = load_session_messages(session_id)
        return jsonify({
            'success': True,
            'session': info,
            'messages': messages
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@llm_bp.route('/sessions/<session_id>/messages', methods=['POST'])
def save_session_messages_endpoint(session_id):
    """保存会话消息"""
    try:
        from services.llmkg.session_service import save_session_messages
        data = request.get_json() or {}
        messages = data.get('messages', [])
        if not isinstance(messages, list):
            return jsonify({'success': False, 'error': 'messages必须是数组'}), 400
        
        success = save_session_messages(session_id, messages)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '保存失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@llm_bp.route('/sessions/<session_id>/title', methods=['PUT'])
def update_session_title_endpoint(session_id):
    """更新会话标题"""
    try:
        from services.llmkg.session_service import update_session_title
        data = request.get_json() or {}
        title = data.get('title', '').strip()
        if not title:
            return jsonify({'success': False, 'error': '标题不能为空'}), 400
        
        success = update_session_title(session_id, title)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '更新失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@llm_bp.route('/sessions/<session_id>', methods=['DELETE'])
def delete_session_endpoint(session_id):
    """删除会话"""
    try:
        from services.llmkg.session_service import delete_session
        success = delete_session(session_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '删除失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@llm_bp.route('/memory/summarize', methods=['POST'])
def summarize_memory_endpoint():
    """总结勾选的消息并保存到memory.jsonl"""
    try:
        from services.llmkg.memory_service import summarize_messages, save_memory
        
        data = request.get_json() or {}
        messages = data.get('messages', [])
        
        if not isinstance(messages, list) or len(messages) == 0:
            return jsonify({'success': False, 'error': '消息列表不能为空'}), 400
        
        # 调用LLM进行总结
        summary_result = summarize_messages(messages)
        if not summary_result.get('success'):
            return jsonify({'success': False, 'error': summary_result.get('error', '总结失败')}), 500
        
        summary = summary_result.get('summary', '')
        if not summary:
            return jsonify({'success': False, 'error': '总结内容为空'}), 500
        
        # 保存到memory.jsonl
        save_result = save_memory(summary, source_messages=messages)
        if not save_result.get('success'):
            return jsonify({'success': False, 'error': save_result.get('error', '保存失败')}), 500
        
        memory_id = save_result.get('memory_id')
        memory = save_result.get('memory')
        
        return jsonify({
            'success': True,
            'memory_id': memory_id,
            'memory': memory
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@llm_bp.route('/memory/update', methods=['POST'])
def update_memory_endpoint():
    """更新记忆到知识库（相似度搜索、关系判断、更新total.jsonl）"""
    try:
        from services.llmkg.memory_service import (
            get_memory_by_id,
            find_similar_memories,
            judge_relationship,
            append_to_text_db
        )
        
        data = request.get_json() or {}
        memory_id = data.get('memory_id')
        
        if not memory_id:
            return jsonify({'success': False, 'error': 'memory_id不能为空'}), 400
        
        # 获取记忆记录
        memory = get_memory_by_id(memory_id)
        if not memory:
            return jsonify({'success': False, 'error': '记忆记录不存在'}), 404
        
        summary = memory.get('summary', '')
        if not summary:
            return jsonify({'success': False, 'error': '记忆总结为空'}), 400
        
        # 在向量数据库中查找相似记忆（top-5）
        similar_result = find_similar_memories(summary, k=5)
        if not similar_result.get('success'):
            return jsonify({'success': False, 'error': similar_result.get('error', '查找相似记忆失败')}), 500
        
        similar_memories = similar_result.get('similar_memories', [])
        
        # 使用LLM判断关系类型
        relationship_result = judge_relationship(summary, similar_memories)
        if not relationship_result.get('success'):
            return jsonify({'success': False, 'error': relationship_result.get('error', '判断关系失败')}), 500
        
        relationship = relationship_result.get('relationship')
        
        # 根据关系类型决定是否添加到total.jsonl
        if relationship == 'high_similarity':
            # 高度相似，不处理
            return jsonify({
                'success': True,
                'relationship': relationship,
                'message': '记忆与已有内容高度相似，未添加到知识库',
                'memory': memory,
                'similar_memories': similar_memories
            })
        elif relationship in ['extension', 'difference']:
            # 补充扩展或存在差异，添加到total.jsonl
            text_data = {
                'id': memory_id,
                'text': summary
            }
            
            append_result = append_to_text_db(text_data)
            if not append_result.get('success'):
                return jsonify({'success': False, 'error': append_result.get('error', '添加到知识库失败')}), 500
            
            relationship_text = '补充扩展' if relationship == 'extension' else '存在差异'
            return jsonify({
                'success': True,
                'relationship': relationship,
                'message': f'记忆已添加到知识库（关系类型：{relationship_text}）',
                'memory': memory,
                'new_id': append_result.get('new_id'),
                'similar_memories': similar_memories
            })
        else:
            return jsonify({
                'success': False,
                'error': f'未知的关系类型: {relationship}'
            }), 500
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


