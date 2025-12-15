from flask import request, jsonify
from services.llmkg.kg_service import neo4j_service
from services.llmkg.audit import audit_cypher
from services.llmkg.schema_store import load_schema, generate_schema_from_import
from .blueprint import kg_bp
import os
import json

@kg_bp.route('/graph', methods=['GET', 'POST'])
def graph_data():
    """获取图数据"""
    default_q = 'MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 100'
    if request.method == 'POST':
        data = request.get_json() or {}
        query = data.get('query', default_q)
    else:
        query = request.args.get('query', default_q)

    try:
        valid, msg, normalized = neo4j_service.validate_readonly_query(query, max_limit=500)
        if not valid:
            return jsonify({'success': False, 'error': msg}), 403

        audit_cypher({
            'endpoint': '/kg/graph',
            'remote_addr': request.remote_addr,
            'query': query,
            'normalized': normalized
        })

        result = neo4j_service.get_graph_data(normalized)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@kg_bp.route('/textdb', methods=['GET'])
def text_db():
    """Return a slice of the local text database for inspection."""
    try:
        import os, json
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'text_data')
        path = os.path.join(base, 'total.jsonl')
        if not os.path.exists(path):
            return jsonify({'success': False, 'error': 'text DB file not found'}), 404

        # try parse as JSON array first, fall back to JSONL
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

        # filtering support
        q = (request.args.get('q') or '').strip()
        if q:
            ql = q.lower()
            filtered = [it for it in data if ql in (it.get('text') or '').lower() or ql in str(it.get('id','')).lower()]
        else:
            filtered = data

        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        slice_ = filtered[offset: offset + limit]
        return jsonify({'success': True, 'count': len(filtered), 'items': slice_})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@kg_bp.route('/textdb/vector_search', methods=['GET'])
def textdb_vector_search():
    """Vector search over text DB."""
    try:
        q = (request.args.get('q') or '').strip()
        if not q:
            return jsonify({'success': False, 'error': 'q is required'}), 400
        k = int(request.args.get('k', 5))
        from services.llmkg import vector_store
        res = vector_store.search(q, k=k)
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@kg_bp.route('/textdb/build_index', methods=['POST'])
def textdb_build_index():
    """Build vector index from local text DB (admin operation)."""
    try:
        data = request.get_json(silent=True) or {}
        model_path = data.get('model_path') or os.getenv('SENT_MODEL_PATH')
        import os as _os
        from services.llmkg import vector_store
        base = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))), 'data', 'text_data')
        path = _os.path.join(base, 'total.jsonl')
        if not _os.path.exists(path):
            return jsonify({'success': False, 'error': 'text DB file not found'}), 404
        # load texts
        with open(path, 'r', encoding='utf-8') as f:
            txt = f.read()
        try:
            texts = json.loads(txt)
        except Exception:
            texts = []
            for line in txt.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    texts.append(json.loads(line))
                except Exception:
                    continue

        if not texts:
            return jsonify({'success': False, 'error': 'no texts to index'}), 400
        if not model_path:
            return jsonify({'success': False, 'error': 'model_path required'}), 400
        vector_store.build_index_from_texts(texts, model_path=model_path)
        return jsonify({'success': True, 'count': len(texts)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@kg_bp.route('/stats', methods=['GET'])
def database_stats():
    """获取数据库统计信息"""
    try:
        node_count = neo4j_service.get_node_count()
        relationship_count = neo4j_service.get_relationship_count()
        labels = neo4j_service.get_labels()
        relationship_types = neo4j_service.get_relationship_types()

        return jsonify({
            'success': True,
            'stats': {
                'node_count': node_count,
                'relationship_count': relationship_count,
                'labels': labels,
                'relationship_types': relationship_types
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@kg_bp.route('/schema', methods=['GET'])
def get_schema():
    """返回图数据库 schema（带缓存标记）。"""
    try:
        schema = load_schema() or {}
        return jsonify({'success': True, 'schema': schema, 'cached': False})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@kg_bp.route('/schema/refresh', methods=['POST'])
def refresh_schema():
    """强制刷新 schema 缓存（从文件加载）。"""
    try:
        schema = load_schema() or {}
        # refresh in-memory cache
        neo4j_service._schema_cache = schema
        neo4j_service._schema_cache_ts = 0
        return jsonify({'success': True, 'schema': schema, 'cached': False})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@kg_bp.route('/schema/rebuild', methods=['POST'])
def rebuild_schema_from_import():
    """读取 import 目录 CSV 生成 schema 文件并返回。"""
    try:
        payload = request.get_json(silent=True) or {}
        import_dir = payload.get('import_dir') if isinstance(payload, dict) else None
        schema = generate_schema_from_import(import_dir=import_dir)
        # refresh cache
        neo4j_service._schema_cache = schema
        neo4j_service._schema_cache_ts = 0
        return jsonify({'success': True, 'schema': schema, 'cached': False})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@kg_bp.route('/query', methods=['POST'])
def execute_query():
    """执行自定义Cypher查询（只读）"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        if not query:
            return jsonify({'success': False, 'error': '查询语句不能为空'}), 400

        valid, msg, normalized = neo4j_service.validate_readonly_query(query, max_limit=500)
        if not valid:
            return jsonify({'success': False, 'error': msg}), 403

        audit_cypher({
            'endpoint': '/kg/query',
            'remote_addr': request.remote_addr,
            'query': query,
            'normalized': normalized
        })

        exec_res = neo4j_service.execute_readonly_query(normalized, params=None, max_rows=500)
        status = 200 if exec_res.get('success') else 400
        return jsonify(exec_res), status
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
