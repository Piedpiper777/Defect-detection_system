import base64
from flask import request, jsonify
from .blueprint import llm_bp
from services.llmkg.llm_service import (
    llm_answer_stream_with_db,
    llm_generate_cypher,
    llm_generate_viz_cypher,
    build_viz_cypher_from_base,
)
from services.llmkg.kg_service import neo4j_service
from flask import Response, stream_with_context

@llm_bp.route('/llm_answer', methods=['POST'])
def llm_answer_endpoint():
    """Streamed: execute DB then stream LLM answer (chunked plain text)"""
    data = request.get_json() or {}
    question = (data.get('question') or '').strip()
    max_rows = int(data.get('max_rows', 200))

    if not question:
        return jsonify({'success': False, 'error': '问题不能为空'}), 400

    # 先生成 Cypher
    gen = llm_generate_cypher(question, max_retries=3, max_limit=max_rows)
    if not gen.get('success'):
        def generate_err():
            yield f"[ERROR] 生成Cypher失败: {gen.get('error')}"
        return Response(stream_with_context(generate_err()), mimetype='text/plain; charset=utf-8')

    cypher = gen.get('cypher', '')
    normalized = gen.get('normalized') or cypher

    # 预执行查询，判断是否有结果以决定是否刷新右侧图谱
    exec_res = neo4j_service.execute_readonly_query(normalized, params=None, max_rows=max_rows)
    has_rows = exec_res.get('success') and exec_res.get('count', 0) > 0

    # 生成可视化友好的语句（节点+关系）；若失败则回退 normalized
    viz_cypher = normalized
    if has_rows:
        viz_gen = llm_generate_viz_cypher(question, normalized, max_retries=2, max_limit=max_rows)
        if viz_gen.get('success'):
            viz_cypher = viz_gen.get('normalized') or viz_gen.get('cypher') or viz_cypher

        # Heuristic fallback: if RETURN only projects properties, rewrite to nodes/relationships for Neovis
        viz_cypher = build_viz_cypher_from_base(viz_cypher or normalized, default_limit=max_rows)

    def generate():
        for chunk in llm_answer_stream_with_db(question, max_rows=max_rows, precomputed=gen, pre_exec_res=exec_res):
            try:
                yield chunk
            except GeneratorExit:
                break

    resp = Response(stream_with_context(generate()), mimetype='text/plain; charset=utf-8')
    # 只有有结果时才把查询传递给前端可视化（使用 Base64 保留中文），使用可视化语句
    if has_rows:
        try:
            b64 = base64.b64encode((viz_cypher or '').encode('utf-8')).decode('ascii')
            resp.headers['X-Cypher-B64'] = b64
        except Exception:
            pass
    return resp



