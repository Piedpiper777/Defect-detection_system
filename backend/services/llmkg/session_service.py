import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

SESSIONS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'sessions')


def ensure_sessions_dir():
    """确保sessions目录存在"""
    os.makedirs(SESSIONS_DIR, exist_ok=True)


def get_session_file_path(session_id: str) -> str:
    """获取会话文件路径"""
    return os.path.join(SESSIONS_DIR, f"{session_id}.jsonl")


def create_session(session_id: Optional[str] = None, title: Optional[str] = None) -> Dict[str, Any]:
    """创建新会话"""
    ensure_sessions_dir()
    
    if not session_id:
        session_id = f"session_{int(datetime.now().timestamp() * 1000)}"
    
    session_file = get_session_file_path(session_id)
    
    # 如果文件已存在，返回现有会话信息
    if os.path.exists(session_file):
        return get_session_info(session_id)
    
    # 创建空会话文件
    with open(session_file, 'w', encoding='utf-8') as f:
        pass  # 创建空文件
    
    # 创建会话元数据
    session_info = {
        'id': session_id,
        'title': title or '新对话',
        'createdAt': datetime.now().isoformat(),
        'updatedAt': datetime.now().isoformat(),
        'messageCount': 0
    }
    
    # 保存元数据到单独的JSON文件
    meta_file = os.path.join(SESSIONS_DIR, f"{session_id}.meta.json")
    with open(meta_file, 'w', encoding='utf-8') as f:
        json.dump(session_info, f, ensure_ascii=False, indent=2)
    
    return session_info


def get_session_info(session_id: str) -> Optional[Dict[str, Any]]:
    """获取会话信息"""
    meta_file = os.path.join(SESSIONS_DIR, f"{session_id}.meta.json")
    if not os.path.exists(meta_file):
        return None
    
    try:
        with open(meta_file, 'r', encoding='utf-8') as f:
            info = json.load(f)
        # 更新消息数量
        messages = load_session_messages(session_id)
        info['messageCount'] = len(messages)
        return info
    except Exception as e:
        logger.error(f"读取会话信息失败 {session_id}: {e}")
        return None


def load_session_messages(session_id: str) -> List[Dict[str, Any]]:
    """加载会话消息（JSONL格式）"""
    session_file = get_session_file_path(session_id)
    if not os.path.exists(session_file):
        return []
    
    messages = []
    try:
        with open(session_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    messages.append(msg)
                except json.JSONDecodeError as e:
                    logger.warning(f"解析消息失败 {session_id}: {e}")
                    continue
    except Exception as e:
        logger.error(f"读取会话消息失败 {session_id}: {e}")
    
    return messages


def save_session_messages(session_id: str, messages: List[Dict[str, Any]]) -> bool:
    """保存会话消息（JSONL格式）"""
    ensure_sessions_dir()
    session_file = get_session_file_path(session_id)
    
    try:
        with open(session_file, 'w', encoding='utf-8') as f:
            for msg in messages:
                json_line = json.dumps(msg, ensure_ascii=False)
                f.write(json_line + '\n')
        
        # 更新会话元数据
        meta_file = os.path.join(SESSIONS_DIR, f"{session_id}.meta.json")
        if os.path.exists(meta_file):
            with open(meta_file, 'r', encoding='utf-8') as f:
                info = json.load(f)
        else:
            info = {'id': session_id, 'title': '新对话'}
        
        info['updatedAt'] = datetime.now().isoformat()
        info['messageCount'] = len(messages)
        
        # 如果第一条消息是用户消息，自动生成标题
        if info.get('title') == '新对话' and messages:
            first_user_msg = next((m for m in messages if m.get('role') == 'user'), None)
            if first_user_msg:
                content = first_user_msg.get('content', '')
                info['title'] = content[:20] + ('...' if len(content) > 20 else '')
        
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        logger.error(f"保存会话消息失败 {session_id}: {e}")
        return False


def update_session_title(session_id: str, title: str) -> bool:
    """更新会话标题"""
    meta_file = os.path.join(SESSIONS_DIR, f"{session_id}.meta.json")
    if not os.path.exists(meta_file):
        return False
    
    try:
        with open(meta_file, 'r', encoding='utf-8') as f:
            info = json.load(f)
        info['title'] = title
        info['updatedAt'] = datetime.now().isoformat()
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"更新会话标题失败 {session_id}: {e}")
        return False


def delete_session(session_id: str) -> bool:
    """删除会话"""
    session_file = get_session_file_path(session_id)
    meta_file = os.path.join(SESSIONS_DIR, f"{session_id}.meta.json")
    
    try:
        if os.path.exists(session_file):
            os.remove(session_file)
        if os.path.exists(meta_file):
            os.remove(meta_file)
        return True
    except Exception as e:
        logger.error(f"删除会话失败 {session_id}: {e}")
        return False


def list_sessions() -> List[Dict[str, Any]]:
    """列出所有会话"""
    ensure_sessions_dir()
    sessions = []
    
    try:
        for filename in os.listdir(SESSIONS_DIR):
            if filename.endswith('.meta.json'):
                session_id = filename[:-10]  # 移除 .meta.json
                info = get_session_info(session_id)
                if info:
                    sessions.append(info)
        
        # 按更新时间倒序排序
        sessions.sort(key=lambda x: x.get('updatedAt', ''), reverse=True)
        return sessions
    except Exception as e:
        logger.error(f"列出会话失败: {e}")
        return []

