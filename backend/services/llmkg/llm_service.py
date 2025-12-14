import os
from dotenv import load_dotenv
from openai import OpenAI
from .kg_service import neo4j_service
from .audit import audit_cypher
from .schema_store import load_schema, FALLBACK_SCHEMA
import re
import json
import logging

load_dotenv()


def _check_literal_entities(query: str):
    """Preflight: for patterns (:Label {name: "xxx"}) ensure such nodes exist.

    Returns (ok: bool, msg: str). Non-blocking on exceptions.
    """
    try:
        matches = re.findall(r":`?([A-Za-z0-9_]+)`?\s*\{\s*name\s*:\s*['\"]([^'\"]+)['\"]\s*\}", query)
        for label, literal in matches:
            cquery = f"MATCH (n:`{label}` {{name: $name}}) RETURN count(n) as c"
            res = neo4j_service.execute_query(cquery, {"name": literal})
            count = res[0]["c"] if res else 0
            if count == 0:
                return False, f"数据库中不存在 {label}.name='{literal}'，请尝试更换名称或使用模糊查询"
        return True, ''
    except Exception as e:
        logging.warning(f"literal check skipped: {e}")
        return True, ''


def llm_generate_cypher(question: str, max_retries: int = 3, max_limit: int = 500) -> dict:
    """Ask the LLM to generate a READ-ONLY Cypher query for the question.

    This function will attempt up to `max_retries` times to get a valid, read-only Cypher
    from the model. Each attempt requests the model to only return a single cypher block
    (```cypher ... ```). After receiving a candidate, the function validates it via
    `neo4j_service.validate_readonly_query()` and returns a normalized query ready for execution.

    Returns dict:
      - on success: {'success': True, 'cypher': original_text, 'normalized': normalized_query}
      - on failure: {'success': False, 'error': reason}
    """
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        return {'success': False, 'error': '未配置 DEEPSEEK_API_KEY 环境变量'}

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    base_system = (
        "你是 Cypher 生成助手。请用中文理解问题，并生成**单条只读**的 Cypher："
        "只允许 MATCH / OPTIONAL MATCH / WHERE / WITH / RETURN / ORDER BY / LIMIT；必须包含 LIMIT 且不超过 {max_limit} 行。"
        "使用现有的节点标签和关系类型，避免编造新的标签或把关系名当作标签。"
        "只输出一个 markdown 代码块 ```cypher ...```，不要有额外文字；若无法安全生成，输出 NO_QUERY。"
    )

    last_err = None
    # 使用文件维护的 schema；若不存在则兜底
    schema = load_schema() or FALLBACK_SCHEMA

    # prepare schema text (short) to include in system prompt (limit length)
    schema_text = ''
    if schema:
        try:
            labels = []
            for l in schema.get('labels', [])[:10]:
                props = list(l.get('properties', {}).keys())[:5]
                labels.append({'label': l.get('label'), 'properties': props})
            rel_types = [r.get('type') for r in schema.get('relationship_types', [])[:10] if r.get('type')]
            schema_text = json.dumps({'labels': labels, 'relationship_types': rel_types}, ensure_ascii=False)
            if len(schema_text) > 1000:
                schema_text = schema_text[:1000] + '...'
        except Exception:
            schema_text = ''

    for attempt in range(1, max_retries + 1):
        try:
            system = base_system.format(max_limit=max_limit)
            if schema_text:
                system += f" Database schema (labels->properties): {schema_text}. Use only existing labels and properties."
            if attempt > 1 and last_err:
                system += f" Previous attempt failed validation: {last_err}. Please correct the query."

            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": question},
            ]
            completion = client.chat.completions.create(model="deepseek-chat", messages=messages, stream=False)
            text = ''
            if getattr(completion, 'choices', None):
                choice0 = completion.choices[0]
                msg = getattr(choice0, 'message', None)
                if isinstance(msg, dict):
                    text = msg.get('content', '')
                else:
                    text = getattr(msg, 'content', '') if msg else ''
            elif isinstance(completion, dict):
                choices = completion.get('choices') or []
                if choices and isinstance(choices[0], dict):
                    text = choices[0].get('message', {}).get('content', '')

            if not text:
                last_err = '模型未返回任何内容'
                logging.warning(f"llm_generate_cypher attempt {attempt}: empty response")
                continue

            # detect NO_QUERY
            if text.strip().upper().startswith('NO_QUERY') or 'NO_QUERY' in text.upper():
                return {'success': False, 'error': '模型判定无法生成查询（NO_QUERY）'}

            # extract code block
            m = re.search(r"```(?:cypher\s*)?([\s\S]*?)```", text, re.IGNORECASE)
            if m:
                cypher = m.group(1).strip()
            else:
                m2 = re.search(r"(MATCH[\s\S]*)", text, re.IGNORECASE)
                cypher = m2.group(1).strip() if m2 else text.strip()

            valid, msg, normalized = neo4j_service.validate_readonly_query(cypher, max_limit=max_limit, schema=schema)
            if not valid:
                last_err = msg
                logging.warning(f"llm_generate_cypher attempt {attempt} invalid: {msg}")
                continue

            # preflight literal existence check here to ensure生成结果可落库
            ok_literal, msg_literal = _check_literal_entities(normalized)
            if not ok_literal:
                last_err = msg_literal
                logging.warning(f"llm_generate_cypher attempt {attempt} literal check failed: {msg_literal}")
                continue

            return {'success': True, 'cypher': cypher, 'normalized': normalized}
        except Exception as e:
            last_err = str(e)
            logging.error(f"llm_generate_cypher attempt {attempt} exception: {last_err}")
            continue

    return {'success': False, 'error': f'生成合法 Cypher 失败: {last_err}'}

def llm_answer_stream_with_db(question: str, max_rows: int = 200):
    """Streamed version of llm_answer_with_db: execute DB, then stream LLM's answer as it is generated."""
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        yield '[ERROR] 未配置 DEEPSEEK_API_KEY 环境变量'
        return

    # Generate cypher
    gen = llm_generate_cypher(question, max_retries=3, max_limit=max_rows)
    if not gen.get('success'):
        yield f"[ERROR] 生成Cypher失败: {gen.get('error')}"
        return

    cypher = gen.get('cypher', '')
    normalized = gen.get('normalized') or cypher
    # final safety check on normalized query (with schema)
    schema = load_schema() or FALLBACK_SCHEMA

    valid, msg, normalized_checked = neo4j_service.validate_readonly_query(normalized, max_limit=max_rows, schema=schema)
    if not valid:
        # fall back to direct LLM stream answer without DB
        try:
            client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
            system = "You are a helpful assistant specialized in industrial defect detection QA. Note: Cypher generation was rejected: %s" % msg
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": question},
            ]
            stream_iter = client.chat.completions.create(model="deepseek-chat", messages=messages, stream=True)
            for event in stream_iter:
                text = ''
                try:
                    if isinstance(event, dict):
                        choices = event.get('choices') or []
                        if choices:
                            delta = choices[0].get('delta') or {}
                            if isinstance(delta, dict):
                                text = delta.get('content', '')
                            else:
                                msg = choices[0].get('message') or {}
                                text = msg.get('content', '')
                        else:
                            text = event.get('text', '')
                    else:
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
            return
        except Exception as e:
            yield f"[ERROR] 生成回答失败: {str(e)}"
            return

    # Preflight: check literal entities exist; if not, return friendly message
    ok_literal, msg_literal = _check_literal_entities(normalized_checked or normalized)
    if not ok_literal:
        yield f"[ERROR] {msg_literal}"
        return

    # Audit the generation before execution
    try:
        audit_cypher({
            'question': question,
            'cypher': cypher,
            'normalized': normalized,
            'schema_fetch': schema if 'schema' in locals() else None,
        })
    except Exception:
        pass

    # Execute the validated query
    exec_res = neo4j_service.execute_readonly_query(normalized, params=None, max_rows=max_rows)
    if not exec_res.get('success'):
        # fallback to LLM direct answer stream with error note
        try:
            client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
            system = "You are a helpful assistant specialized in industrial defect detection QA. Database query execution failed: %s" % exec_res.get('error')
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": question},
            ]
            stream_iter = client.chat.completions.create(model="deepseek-chat", messages=messages, stream=True)
            for event in stream_iter:
                text = ''
                try:
                    if isinstance(event, dict):
                        choices = event.get('choices') or []
                        if choices:
                            delta = choices[0].get('delta') or {}
                            if isinstance(delta, dict):
                                text = delta.get('content', '')
                            else:
                                msg = choices[0].get('message') or {}
                                text = msg.get('content', '')
                        else:
                            text = event.get('text', '')
                    else:
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
            return
        except Exception as e:
            yield f"[ERROR] 生成回答失败: {str(e)}"
            return

    # Prepare prompt with sample rows and stream final answer
    sample = exec_res.get('results', [])[:10]
    rows_text = ''
    for r in sample:
        rows_text += str(r) + '\n'

    try:
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        system = "You are an assistant that answers user questions using query results. Use the provided sample rows to craft a concise, accurate, and human-friendly answer. If results are insufficient, say so."
        user_prompt = f"User question:\n{question}\n\nCypher executed:\n{normalized}\n\nSample results (first {len(sample)} rows):\n{rows_text}"
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ]

        stream_iter = client.chat.completions.create(model="deepseek-chat", messages=messages, stream=True)
        for event in stream_iter:
            text = ''
            try:
                if isinstance(event, dict):
                    choices = event.get('choices') or []
                    if choices:
                        delta = choices[0].get('delta') or {}
                        if isinstance(delta, dict):
                            text = delta.get('content', '')
                        else:
                            msg = choices[0].get('message') or {}
                            text = msg.get('content', '')
                    else:
                        text = event.get('text', '')
                else:
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
        yield f"[ERROR] 生成回答失败: {str(e)}"
