import logging
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

def llm_answer_service(question: str) -> dict:
    """调用大模型进行问答，返回字典结果"""
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        return {'success': False, 'error': '未配置 DEEPSEEK_API_KEY 环境变量'}

    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        messages = [
            {"role": "system", "content": "You are a helpful assistant specialized in industrial defect detection QA."},
            {"role": "user", "content": question},
        ]
        completion = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            stream=False,
        )

        answer = completion.choices[0].message.content if completion.choices else ""
        return {'success': True, 'answer': answer}
    except Exception as e:
        logging.error(f"大模型调用失败: {str(e)}")
        return {'success': False, 'error': str(e)}


def llm_answer_stream(question: str):
    """以生成器方式流式返回模型输出片段（yield 字符串片段）"""
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        yield '[ERROR] 未配置 DEEPSEEK_API_KEY 环境变量'
        return

    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        messages = [
            {"role": "system", "content": "You are a helpful assistant specialized in industrial defect detection QA."},
            {"role": "user", "content": question},
        ]

        # 使用流式接口
        stream_iter = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            stream=True,
        )

        for event in stream_iter:
            # 尽量兼容不同返回结构
            text = ''
            try:
                # dict-like
                if isinstance(event, dict):
                    choices = event.get('choices') or []
                    if choices:
                        delta = choices[0].get('delta') or {}
                        if isinstance(delta, dict):
                            text = delta.get('content', '')
                        else:
                            # sometimes full message
                            msg = choices[0].get('message') or {}
                            text = msg.get('content', '')
                    else:
                        text = event.get('text', '')
                else:
                    # object with attributes
                    choices = getattr(event, 'choices', None)
                    if choices:
                        choice0 = choices[0]
                        delta = getattr(choice0, 'delta', None)
                        if delta:
                            text = getattr(delta, 'content', '')
                        else:
                            msg = getattr(choice0, 'message', None)
                            if msg:
                                text = getattr(msg, 'content', '')
                    else:
                        text = getattr(event, 'text', '') or ''
            except Exception:
                text = ''

            if text:
                yield text

    except Exception as e:
        logging.error(f"流式调用失败: {str(e)}")
        yield f'[ERROR] {str(e)}'
