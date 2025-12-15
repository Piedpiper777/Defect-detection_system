import os
import json
import threading
import re
from typing import List, Dict, Any, Optional

import numpy as np

try:
    import faiss
except Exception:
    faiss = None

try:
    from text2vec import SentenceModel
except Exception:
    SentenceModel = None
    
VEC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "vector_database")
INDEX_FILE = os.path.join(VEC_DIR, "index.faiss")
META_FILE = os.path.join(VEC_DIR, "metadata.json")

_index = None
_meta: List[Dict[str, Any]] = []
_model = None
_lock = threading.Lock()


def ensure_dir():
    os.makedirs(VEC_DIR, exist_ok=True)


def load_model(model_path: str = None):
    global _model
    if _model is not None:
        return _model
    if SentenceModel is None:
        raise RuntimeError("text2vec (SentenceModel) is not installed")
    # fallback to environment variable if not provided
    if model_path is None:
        model_path = os.getenv('SENT_MODEL_PATH')
    if model_path is None:
        raise RuntimeError("model_path is required for text2vec SentenceModel (or set SENT_MODEL_PATH env var)")
    _model = SentenceModel(model_path)
    return _model


def build_index_from_texts(texts: List[Dict[str, Any]], model_path: str, index_path: str = INDEX_FILE, meta_path: str = META_FILE, batch_size: int = 64):
    """Build FAISS index from list of {'id','text'} dicts."""
    if faiss is None:
        raise RuntimeError("faiss is not installed")
    ensure_dir()
    model = load_model(model_path)
    corpus = [t.get('text', '') for t in texts]
    embeddings = model.encode(corpus, batch_size=batch_size)
    emb_arr = np.asarray(embeddings, dtype='float32')
    if emb_arr.ndim == 1:
        emb_arr = emb_arr.reshape(1, -1)
    # normalize for cosine similarity using numpy
    norms = np.linalg.norm(emb_arr, axis=1, keepdims=True)
    norms[norms == 0] = 1  # Avoid division by zero
    emb_arr = emb_arr / norms
    dim = emb_arr.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(emb_arr)
    faiss.write_index(index, index_path)
    # write metadata
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(texts, f, ensure_ascii=False, indent=2)
    # reload into memory
    with _lock:
        global _index, _meta
        _index = index
        _meta = texts
    return True


def build_index_from_file(path: str, model_path: str, index_path: str = INDEX_FILE, meta_path: str = META_FILE, batch_size: int = 64):
    """Load texts from a file (JSON or JSONL) and build index."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    try:
        data = json.loads(text)
    except Exception:
        data = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data.append(json.loads(line))
            except Exception:
                continue
    return build_index_from_texts(data, model_path=model_path, index_path=index_path, meta_path=meta_path, batch_size=batch_size)


def _parse_args_and_build():
    import argparse
    parser = argparse.ArgumentParser(description='Build FAISS index from text DB file')
    parser.add_argument('--model-path', required=True, help='Local text2vec model path (e.g. models/Jerry0/text2vec-base-chinese)')
    parser.add_argument('--data', default=os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'text_data', 'total.jsonl'))
    args = parser.parse_args()
    print(f'Indexing from {args.data} using model {args.model_path}...')
    build_index_from_file(args.data, args.model_path)
    print('Index built and saved.')


if __name__ == '__main__':
    _parse_args_and_build()


def load_index(index_path: str = INDEX_FILE, meta_path: str = META_FILE):
    """Load index and metadata into memory."""
    global _index, _meta
    ensure_dir()
    if faiss is None:
        raise RuntimeError("faiss is not installed")
    if not os.path.exists(index_path) or not os.path.exists(meta_path):
        return False
    idx = faiss.read_index(index_path)
    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = json.load(f)
    with _lock:
        _index = idx
        _meta = meta
    return True


def index_exists(index_path: str = INDEX_FILE, meta_path: str = META_FILE) -> bool:
    """Return True if both index and metadata files exist on disk."""
    return os.path.exists(index_path) and os.path.exists(meta_path)


def search(query: str, k: int = 5, model_path: Optional[str] = None, threshold: float = 0.0) -> Dict[str, Any]:
    """Search the vector DB using `text2vec.SentenceModel` for embeddings.

    Args:
        query: Search query
        k: Number of results to return
        model_path: Path to the embedding model
        threshold: Minimum similarity score threshold (0.0-1.0)
    """
    if faiss is None:
        return {'success': False, 'error': 'faiss not installed'}

    if _index is None:
        ok = load_index()
        if not ok:
            return {'success': False, 'error': 'index not found'}

    try:
        model = load_model(model_path)
    except Exception as e:
        return {'success': False, 'error': f'load_model error: {e}'}

    try:
        q_emb = model.encode([query], batch_size=1)
    except Exception as e:
        return {'success': False, 'error': f'embed error: {e}'}

    # Ensure q_emb is a numpy array with correct dtype
    q_arr = np.asarray(q_emb, dtype='float32')
    if q_arr.ndim == 1:
        q_arr = q_arr.reshape(1, -1)

    # Normalize using numpy (faiss.normalize_L2 has issues)
    norms = np.linalg.norm(q_arr, axis=1, keepdims=True)
    norms[norms == 0] = 1  # Avoid division by zero
    q_arr = q_arr / norms

    # Ensure array is contiguous for faiss
    q_arr = np.ascontiguousarray(q_arr)

    # 智能调整检索数量：检索更多结果进行筛选
    search_k = min(k * 3, len(_meta)) if len(_meta) > 0 else k

    # Use faiss search method - try simple approach first
    try:
        D, I = _index.search(q_arr, search_k)
    except Exception:
        # Fallback to manual allocation if the above fails
        D = np.empty((q_arr.shape[0], search_k), dtype=np.float32)
        I = np.empty((q_arr.shape[0], search_k), dtype=np.int64)
        _index.search(q_arr, search_k, D, I)

    results = []
    for score, idx in zip(D[0].tolist(), I[0].tolist()):
        if 0 <= idx < len(_meta) and score >= threshold:
            item = _meta[idx]
            results.append({'score': float(score), 'item': item})

    # 按相似度降序排序并限制结果数量
    results.sort(key=lambda x: x['score'], reverse=True)
    results = results[:k]

    return {'success': True, 'results': results}


def search_enhanced(query: str, k: int = 5, model_path: Optional[str] = None) -> Dict[str, Any]:
    """Enhanced search with intelligent query expansion and filtering."""
    if faiss is None:
        return {'success': False, 'error': 'faiss not installed'}

    # 基本搜索
    base_results = search(query, k=k*2, model_path=model_path, threshold=0.1)

    if not base_results.get('success'):
        return base_results

    results = base_results['results']

    # 智能筛选和重新排序
    filtered_results = []
    seen_texts = set()

    for result in results:
        item = result['item']
        text = item.get('text', '').strip()

        # 去重：避免相似文本重复
        if text in seen_texts:
            continue
        seen_texts.add(text)

        # 基于内容质量的评分调整
        score = result['score']
        text_len = len(text)

        # 偏好中等长度的文本（太短可能信息不足，太长可能包含无关信息）
        if 50 <= text_len <= 500:
            score *= 1.1
        elif text_len < 30:
            score *= 0.8

        # 偏好包含具体解决方案的文本
        if any(keyword in text for keyword in ['解决方案', '解决方法', '可采取', '优化', '调整']):
            score *= 1.05

        filtered_results.append({
            'score': score,
            'item': item,
            'relevance_boost': score > result['score']
        })

    # 重新排序
    filtered_results.sort(key=lambda x: x['score'], reverse=True)
    final_results = filtered_results[:k]

    return {
        'success': True,
        'results': [{'score': r['score'], 'item': r['item']} for r in final_results],
        'stats': {
            'total_found': len(results),
            'filtered': len(final_results),
            'avg_score': sum(r['score'] for r in final_results) / len(final_results) if final_results else 0
        }
    }
