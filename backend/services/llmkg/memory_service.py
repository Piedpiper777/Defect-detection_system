import os
import json
import logging
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

MEMORY_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'memory')
MEMORY_FILE = os.path.join(MEMORY_DIR, 'memory.jsonl')
TEXT_DB_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'text_data', 'total.jsonl')

# 文件操作锁
_file_lock = threading.Lock()


def ensure_memory_dir():
    """确保memory目录存在"""
    os.makedirs(MEMORY_DIR, exist_ok=True)


def summarize_messages(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """调用LLM对勾选的消息进行总结
    
    Args:
        messages: 消息列表，格式 [{"role": "user", "content": "..."}, ...]
    
    Returns:
        {
            'success': bool,
            'summary': str,  # 总结内容
            'error': str     # 错误信息（如果有）
        }
    """
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        return {'success': False, 'error': '未配置 DEEPSEEK_API_KEY 环境变量'}
    
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        
        # 构建prompt
        system_prompt = (
            "你是一个知识总结助手。请对用户提供的对话消息进行总结，"
            "提取关键信息和知识点，生成一段简洁、准确、结构化的总结文本。"
            "总结应该：1) 保留核心信息 2) 去除冗余内容 3) 保持逻辑清晰 4) 使用专业术语"
        )
        
        # 将消息转换为文本
        messages_text = ""
        for msg in messages:
            role = msg.get('role', '')
            content = msg.get('content', '')
            if role == 'user':
                messages_text += f"用户: {content}\n\n"
            elif role == 'assistant':
                messages_text += f"助手: {content}\n\n"
        
        user_prompt = f"请对以下对话进行总结：\n\n{messages_text}"
        
        llm_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        completion = client.chat.completions.create(
            model="deepseek-chat",
            messages=llm_messages,
            stream=False
        )
        
        # 提取回复
        summary = ""
        if hasattr(completion, 'choices') and completion.choices:
            msg = completion.choices[0].message
            if isinstance(msg, dict):
                summary = msg.get('content', '')
            else:
                summary = getattr(msg, 'content', '')
        
        if not summary:
            return {'success': False, 'error': 'LLM未返回总结内容'}
        
        return {'success': True, 'summary': summary.strip()}
        
    except Exception as e:
        logger.error(f"总结消息失败: {e}")
        return {'success': False, 'error': str(e)}


def save_memory(summary: str, source_messages: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """保存记忆总结到memory.jsonl
    
    Args:
        summary: 总结内容
        source_messages: 原始消息（可选）
    
    Returns:
        {
            'success': bool,
            'memory_id': str,  # 记忆ID
            'error': str
        }
    """
    ensure_memory_dir()
    
    try:
        memory_id = f"memory_{int(datetime.now().timestamp() * 1000)}"
        memory_record = {
            'id': memory_id,
            'summary': summary,
            'createdAt': datetime.now().isoformat(),
            'source_messages': source_messages if source_messages else []
        }
        
        with _file_lock:
            with open(MEMORY_FILE, 'a', encoding='utf-8') as f:
                json_line = json.dumps(memory_record, ensure_ascii=False)
                f.write(json_line + '\n')
        
        logger.info(f"保存记忆成功: {memory_id}")
        return {'success': True, 'memory_id': memory_id, 'memory': memory_record}
        
    except Exception as e:
        logger.error(f"保存记忆失败: {e}")
        return {'success': False, 'error': str(e)}


def find_similar_memories(summary: str, k: int = 5) -> Dict[str, Any]:
    """在向量数据库中查找相似记忆
    
    Args:
        summary: 要查找的总结内容
        k: 返回top-k结果
    
    Returns:
        {
            'success': bool,
            'similar_memories': List[Dict],  # 相似记忆列表
            'error': str
        }
    """
    try:
        from .vector_store import search_enhanced, index_exists
        
        if not index_exists():
            return {'success': False, 'error': '向量索引不存在'}
        
        # 获取模型路径
        model_path = os.getenv('SENT_MODEL_PATH')
        if not model_path:
            default_model_path = os.path.join(
                os.path.dirname(__file__), '..', '..', '..', 
                'models', 'Jerry0', 'text2vec-base-chinese'
            )
            model_path = default_model_path if os.path.exists(default_model_path) else None
        
        if not model_path:
            return {'success': False, 'error': '未配置SENT_MODEL_PATH且找不到默认模型'}
        
        # 搜索相似记忆
        search_result = search_enhanced(summary, k=k, model_path=model_path)
        
        if not search_result.get('success'):
            return {'success': False, 'error': search_result.get('error', '搜索失败')}
        
        similar_memories = []
        for result in search_result.get('results', []):
            item = result.get('item', {})
            similar_memories.append({
                'id': item.get('id'),
                'text': item.get('text', ''),
                'score': result.get('score', 0.0)
            })
        
        return {
            'success': True,
            'similar_memories': similar_memories
        }
        
    except Exception as e:
        logger.error(f"查找相似记忆失败: {e}")
        return {'success': False, 'error': str(e)}


def judge_relationship(new_memory: str, similar_memories: List[Dict[str, Any]]) -> Dict[str, Any]:
    """使用LLM判断新记忆与相似记忆的关系类型
    
    Args:
        new_memory: 新的记忆总结
        similar_memories: 相似记忆列表
    
    Returns:
        {
            'success': bool,
            'relationship': str,  # 'high_similarity' | 'extension' | 'difference'
            'reasoning': str,     # 判断理由
            'error': str
        }
    """
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        return {'success': False, 'error': '未配置 DEEPSEEK_API_KEY 环境变量'}
    
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        
        # 构建相似记忆文本
        similar_texts = ""
        for i, mem in enumerate(similar_memories[:5], 1):
            similar_texts += f"{i}. [ID: {mem.get('id', 'unknown')}] {mem.get('text', '')}\n"
        
        system_prompt = (
            "你是一个知识关系判断助手。请分析新记忆与已有记忆的关系，"
            "判断关系类型。关系类型有三种：\n"
            "1. high_similarity（高度相似）：新记忆与已有记忆内容高度重复，没有新增信息\n"
            "2. extension（补充扩展）：新记忆是对已有记忆的补充、扩展或细化，有新增价值\n"
            "3. difference（存在差异）：新记忆与已有记忆存在明显差异或矛盾\n\n"
            "请只返回关系类型（high_similarity/extension/difference），不要有其他文字。"
        )
        
        user_prompt = (
            f"新记忆：\n{new_memory}\n\n"
            f"已有相似记忆：\n{similar_texts}\n\n"
            "请判断新记忆与已有记忆的关系类型。"
        )
        
        llm_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        completion = client.chat.completions.create(
            model="deepseek-chat",
            messages=llm_messages,
            stream=False
        )
        
        # 提取回复
        response = ""
        if hasattr(completion, 'choices') and completion.choices:
            msg = completion.choices[0].message
            if isinstance(msg, dict):
                response = msg.get('content', '')
            else:
                response = getattr(msg, 'content', '')
        
        response = response.strip().lower()
        
        # 解析关系类型
        relationship = None
        if 'high_similarity' in response or '高度相似' in response:
            relationship = 'high_similarity'
        elif 'extension' in response or '补充扩展' in response or '补充' in response:
            relationship = 'extension'
        elif 'difference' in response or '存在差异' in response or '差异' in response:
            relationship = 'difference'
        else:
            # 默认判断：如果无法确定，使用相似度阈值
            # 如果最高相似度>0.9，认为是high_similarity
            max_score = max([m.get('score', 0) for m in similar_memories], default=0)
            if max_score > 0.9:
                relationship = 'high_similarity'
            elif max_score > 0.7:
                relationship = 'extension'
            else:
                relationship = 'difference'
        
        return {
            'success': True,
            'relationship': relationship,
            'reasoning': response,
            'max_similarity_score': max([m.get('score', 0) for m in similar_memories], default=0)
        }
        
    except Exception as e:
        logger.error(f"判断关系失败: {e}")
        return {'success': False, 'error': str(e)}


def append_to_text_db(memory_data: Dict[str, Any]) -> Dict[str, Any]:
    """将记忆数据追加到total.jsonl（按JSONL格式，每行一个JSON对象）
    
    Args:
        memory_data: 记忆数据，格式 {"id": "...", "text": "..."}，如果id为空则自动生成
    
    Returns:
        {
            'success': bool,
            'new_id': str,  # 新生成的ID
            'error': str
        }
    """
    try:
        # 读取现有数据（支持JSON数组和JSONL两种格式）
        existing_data = []
        if os.path.exists(TEXT_DB_FILE):
            with _file_lock:
                with open(TEXT_DB_FILE, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        try:
                            # 尝试解析为JSON数组
                            existing_data = json.loads(content)
                            if not isinstance(existing_data, list):
                                existing_data = []
                        except json.JSONDecodeError:
                            # 如果不是JSON数组，按行解析JSONL
                            existing_data = []
                            for line in content.split('\n'):
                                line = line.strip()
                                if line:
                                    try:
                                        existing_data.append(json.loads(line))
                                    except json.JSONDecodeError:
                                        continue
        
        # 如果没有提供ID，自动生成
        if not memory_data.get('id'):
            # 找到最大ID
            max_id = 0
            for item in existing_data:
                if isinstance(item, dict):
                    item_id = item.get('id', '')
                    # 尝试解析为数字
                    try:
                        if str(item_id).isdigit():
                            max_id = max(max_id, int(item_id))
                    except (ValueError, AttributeError):
                        pass
            memory_data['id'] = str(max_id + 1)
        
        # 检查是否已存在相同ID
        existing_ids = {str(item.get('id')) for item in existing_data if isinstance(item, dict)}
        if str(memory_data.get('id')) in existing_ids:
            # ID已存在，生成新ID
            max_id = 0
            for item in existing_data:
                if isinstance(item, dict):
                    item_id = item.get('id', '')
                    try:
                        if str(item_id).isdigit():
                            max_id = max(max_id, int(item_id))
                    except (ValueError, AttributeError):
                        pass
            memory_data['id'] = str(max_id + 1)
        
        # 追加新数据到列表
        existing_data.append(memory_data)
        
        # 按JSONL格式写回文件（每行一个JSON对象）
        with _file_lock:
            with open(TEXT_DB_FILE, 'w', encoding='utf-8') as f:
                for item in existing_data:
                    json_line = json.dumps(item, ensure_ascii=False)
                    f.write(json_line + '\n')
        
        logger.info(f"追加数据到text_db成功: {memory_data.get('id')}")
        return {'success': True, 'new_id': memory_data.get('id')}
        
    except Exception as e:
        logger.error(f"追加数据到text_db失败: {e}")
        return {'success': False, 'error': str(e)}


def get_memory_by_id(memory_id: str) -> Optional[Dict[str, Any]]:
    """根据ID获取记忆记录"""
    if not os.path.exists(MEMORY_FILE):
        return None
    
    try:
        with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    memory = json.loads(line)
                    if memory.get('id') == memory_id:
                        return memory
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.error(f"读取记忆失败: {e}")
    
    return None

