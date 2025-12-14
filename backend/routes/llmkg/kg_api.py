from flask import request, jsonify
from services.llmkg.kg_service import neo4j_service
from .blueprint import kg_bp

@kg_bp.route('/graph', methods=['GET', 'POST'])
def graph_data():
    """获取图数据"""
    if request.method == 'POST':
        data = request.get_json()
        query = data.get('query', 'MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 100')
    else:
        query = request.args.get('query', 'MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 100')

    try:
        result = neo4j_service.get_graph_data(query)
        if result['success']:
            return jsonify(result)
        else:
            return jsonify(result), 400
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

@kg_bp.route('/query', methods=['POST'])
def execute_query():
    """执行自定义Cypher查询（只读）"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        if not query:
            return jsonify({'success': False, 'error': '查询语句不能为空'}), 400

        query_upper = query.upper().strip()
        if query_upper.startswith(('CREATE', 'MERGE', 'SET', 'DELETE', 'REMOVE', 'DROP')):
            return jsonify({'success': False, 'error': '只允许执行只读查询'}), 403

        records = neo4j_service.execute_query(query)
        results = []
        for record in records:
            result_dict = {}
            for key, value in record.items():
                if hasattr(value, 'labels'):
                    result_dict[key] = {
                        'type': 'node',
                        'id': value.id,
                        'labels': list(value.labels),
                        'properties': dict(value)
                    }
                elif hasattr(value, 'type'):
                    result_dict[key] = {
                        'type': 'relationship',
                        'id': value.id,
                        'type': value.type,
                        'start_node': value.start_node.id,
                        'end_node': value.end_node.id,
                        'properties': dict(value)
                    }
                else:
                    result_dict[key] = value
            results.append(result_dict)
        return jsonify({'success': True, 'results': results, 'count': len(results)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
