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
        if test_mode:
            # Simulated end-to-end flow for testing without external LLM/Neo4j
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
        else:
            for chunk in llm_answer_stream_with_db(question, max_rows=max_rows):
                try:
                    yield chunk
                except GeneratorExit:
                    break

    resp = Response(stream_with_context(generate()), mimetype='text/plain; charset=utf-8')
    # send viz cypher header if available
    if viz_cypher:
        try:
            b64 = base64.b64encode((viz_cypher or '').encode('utf-8')).decode('ascii')
            resp.headers['X-Cypher-B64'] = b64
        except Exception:
            pass
    return resp



