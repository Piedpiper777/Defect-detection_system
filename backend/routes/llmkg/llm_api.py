from flask import request, jsonify
from services.llmkg.llm_service import llm_answer_service
from .blueprint import llm_bp
from services.llmkg.llm_service import llm_answer_stream
from flask import Response, stream_with_context

@llm_bp.route('/llm_answer', methods=['POST'])
def llm_answer():
    """调用大模型进行问答"""
    data = request.get_json() or {}
    question = (data.get('question') or '').strip()

    if not question:
        return jsonify({'success': False, 'error': '问题不能为空'}), 400

    result = llm_answer_service(question)
    status_code = 200 if result.get('success') else 500
    return jsonify(result), status_code


@llm_bp.route('/llm_stream', methods=['POST'])
def llm_answer_stream_endpoint():
    """流式返回大模型回答（chunked plain text）"""
    data = request.get_json() or {}
    question = (data.get('question') or '').strip()

    if not question:
        return jsonify({'success': False, 'error': '问题不能为空'}), 400

    def generate():
        for chunk in llm_answer_stream(question):
            # 每个 chunk 直接发送，前端做追加显示
            try:
                yield chunk
            except GeneratorExit:
                break

    return Response(stream_with_context(generate()), mimetype='text/plain; charset=utf-8')
