from flask import request, jsonify
from .blueprint import llm_bp
from services.llmkg.llm_service import llm_answer_stream_with_db
from flask import Response, stream_with_context

@llm_bp.route('/llm_answer', methods=['POST'])
def llm_answer_endpoint():
    """Streamed: execute DB then stream LLM answer (chunked plain text)"""
    data = request.get_json() or {}
    question = (data.get('question') or '').strip()
    max_rows = int(data.get('max_rows', 200))

    if not question:
        return jsonify({'success': False, 'error': '问题不能为空'}), 400

    def generate():
        for chunk in llm_answer_stream_with_db(question, max_rows=max_rows):
            try:
                yield chunk
            except GeneratorExit:
                break

    return Response(stream_with_context(generate()), mimetype='text/plain; charset=utf-8')



