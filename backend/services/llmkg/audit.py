import os
import json
import time
import logging

AUDIT_PATH = os.getenv('KG_AUDIT_PATH', os.path.join(os.path.dirname(__file__), '..', '..', 'logs', 'cypher_audit.log'))

os.makedirs(os.path.dirname(AUDIT_PATH), exist_ok=True)


def audit_cypher(entry: dict):
    """Append an audit entry as a JSON line to the configured audit file."""
    try:
        payload = entry.copy()
        if 'timestamp' not in payload:
            payload['timestamp'] = int(time.time())
        with open(AUDIT_PATH, 'a', encoding='utf-8') as f:
            # default=str 避免 Neo4j DateTime 等不可序列化对象报错
            f.write(json.dumps(payload, ensure_ascii=False, default=str) + '\n')
    except Exception as e:
        logging.exception(f'无法写入审计日志: {e}')
