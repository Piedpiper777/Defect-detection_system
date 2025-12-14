from neo4j import GraphDatabase
from dotenv import load_dotenv
import logging
import time
import os
from .schema_store import load_schema

load_dotenv()


def schema_lookup_prop_type(schema: dict, label: str, prop: str):
    """Lookup inferred type for a property on a given label in schema."""
    try:
        for l in schema.get('labels', []):
            if l.get('label') == label:
                props = l.get('properties', {})
                p = props.get(prop)
                if p:
                    return p.get('inferred_type')
    except Exception:
        return None
    return None

class Neo4jService:
    """Neo4j服务类，封装连接与基本操作"""
    def __init__(self, uri=None, user=None, password=None,
                 max_retries=10, retry_interval=3):
        self.uri = uri or os.getenv("NEO4J_URI")
        self.user = user or os.getenv("NEO4J_USER")
        self.password = password or os.getenv("NEO4J_PASSWORD")
        if not self.uri or not self.user or not self.password:
            raise ValueError("Neo4j 配置缺失：请在环境变量或初始化参数中提供 NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD。")
        self.driver = None
        self.connected = False
        self.max_retries = max_retries
        self.retry_interval = retry_interval
        skip_connect = os.getenv('KG_SKIP_CONNECT', '0').lower() in ('1', 'true', 'yes')
        if not skip_connect:
            self.connect()
        else:
            logging.info('跳过 Neo4j 自动连接（KG_SKIP_CONNECT 设置）')
        # Schema file cache (read-only)
        self._schema_cache = None
        self._schema_cache_ts = 0
        self.schema_ttl = int(os.getenv('KG_SCHEMA_TTL', '300'))

    def connect(self):
        for attempt in range(1, self.max_retries + 1):
            try:
                self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
                with self.driver.session() as session:
                    session.run("RETURN 1")
                self.connected = True
                logging.info("成功连接到Neo4j数据库")
                return
            except Exception as e:
                self.connected = False
                logging.warning(f"Neo4j连接失败，第{attempt}/{self.max_retries}次重试: {str(e)}")
                if attempt == self.max_retries:
                    logging.error("Neo4j在最大重试次数后仍不可用，终止启动")
                    raise e
                time.sleep(self.retry_interval)

    def close(self):
        if self.driver:
            self.driver.close()
            logging.info("Neo4j连接已关闭")
        self.connected = False

    def execute_query(self, query, parameters=None):
        try:
            with self.driver.session() as session:
                result = session.run(query, parameters or {})
                return [record for record in result]
        except Exception as e:
            logging.error(f"查询执行失败: {str(e)}")
            raise e

    def get_graph_data(self, query="MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 100"):
        """ 获取初始图数据 """
        try:
            records = self.execute_query(query)
            nodes, edges = [], []
            node_ids, edge_ids = set(), set()
            for record in records:
                for node_key in ['n', 'm']:
                    if node_key in record.keys():
                        node = record[node_key]
                        if node.id not in node_ids:
                            prop_dict = dict(node)
                            caption = prop_dict.get('name') or (list(node.labels)[0] if node.labels else 'Node')
                            nodes.append({
                                'id': node.id,
                                'label': list(node.labels)[0] if node.labels else 'Node',
                                'caption': caption,
                                'properties': prop_dict
                            })
                            node_ids.add(node.id)
                if 'r' in record.keys():
                    relationship = record['r']
                    if relationship.id not in edge_ids:
                        edges.append({
                            'id': relationship.id,
                            'from': relationship.start_node.id,
                            'to': relationship.end_node.id,
                            'label': relationship.type,
                            'properties': dict(relationship)
                        })
                        edge_ids.add(relationship.id)
            return {'nodes': nodes, 'edges': edges, 'success': True}
        except Exception as e:
            return {'error': str(e), 'success': False}

    def validate_readonly_query(self, query: str, max_limit: int = 500, schema: dict = None):
        """
        Validate that a Cypher query is read-only and enforce a maximum LIMIT.
        Returns a tuple: (valid: bool, message: str, normalized_query: str)
        """
        import re

        if not query or not isinstance(query, str):
            return False, '查询语句必须为非空字符串', None

        q = query.strip().rstrip(';')

        # 禁止危险关键词或对数据库管理的调用
        forbidden_pattern = re.compile(r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DROP|CALL\s+dbms|CALL\s+apoc|CALL\s+db\.|CALL\s+dbms)\b",
                                       re.IGNORECASE)
        if forbidden_pattern.search(q):
            return False, '仅允许执行只读查询（禁止 CREATE/MERGE/SET/DELETE/REMOVE/DROP/CALL dbms/apoc 等）', None

        # 强制并规范 LIMIT
        limit_match = re.search(r"\bLIMIT\s+(\d+)\b", q, re.IGNORECASE)
        if limit_match:
            limit_val = int(limit_match.group(1))
            if limit_val > max_limit:
                q = re.sub(r"\bLIMIT\s+\d+\b", f"LIMIT {max_limit}", q, flags=re.IGNORECASE)
        else:
            q = q + f" LIMIT {max_limit}"

        # 从文件 schema 填充（非阻断检查）
        if schema is None:
            schema = load_schema() or {}

        if schema:
            try:
                # collect known labels and relationship types
                known_labels = {l['label'] for l in schema.get('labels', [])}
                known_rels = {r.get('type') for r in schema.get('relationship_types', [])}
                # collect property names per label
                prop_map = {}
                for l in schema.get('labels', []):
                    pname_map = set(l.get('properties', {}).keys())
                    prop_map[l.get('label')] = pname_map

                # find labels used in query
                labels_used = set(re.findall(r":`?([A-Za-z0-9_]+)`?", q))
                # Some models mistakenly use relationship type names as labels; allow if it matches a known relationship type
                allowed_as_label = known_labels.union(known_rels)
                unknown_labels = labels_used - allowed_as_label
                if unknown_labels:
                    # 某些生成结果会将关系名/短语误用为 label，放宽为警告但不拦截
                    logging.warning(f"validate_readonly_query: unknown labels tolerated: {','.join(sorted(unknown_labels))}")

                # find relationship types used in query (e.g. -[:REL]- or -[r:REL]-)
                rels_used = set(re.findall(r":`?([A-Za-z0-9_]+)`?\s*\]", q))
                unknown_rels = rels_used - known_rels
                if unknown_rels:
                    return False, f'使用了未知的关系类型: {",".join(sorted(unknown_rels))}', None

                # find property accesses like n.prop and do basic existence/type checks
                prop_accesses = re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\.(`?[A-Za-z0-9_]+`?)", q)
                # build union of all known props for a quick existence check
                all_props = set().union(*[s for s in prop_map.values()]) if prop_map else set()
                for var, prop in prop_accesses:
                    prop = prop.strip('`')
                    if prop not in all_props:
                        return False, f'使用了未知的属性: {prop}', None

                # simple numeric comparison check: e.g. n.age > 10 while age inferred as string
                num_comp = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\.([A-Za-z0-9_]+)\s*(=|>|>=|<|<=)\s*([0-9]+(?:\.[0-9]+)?)", q)
                for prop, op, num in num_comp:
                    # try to find inferred type for prop
                    inferred = None
                    for lname, props in prop_map.items():
                        if prop in props:
                            # look up inferred type
                            inferred = schema_lookup_prop_type(schema, lname, prop)
                            break
                    if inferred == 'string':
                        return False, f'属性 {prop} 类型被推断为 string，但在比较中使用了数字常量', None
            except Exception:
                # if anything goes wrong in schema-check, fall back to conservative behavior (do not block)
                logging.exception('在 schema 校验阶段发生异常，跳过额外校验')

        return True, '', q

    def execute_readonly_query(self, query: str, params: dict = None, max_rows: int = 500):
        """Execute a validated read-only Cypher query and serialize results.

        Returns dict: {'success': True, 'results': [...], 'count': n, 'query': executed_query}
        """
        try:
            valid, msg, normalized = self.validate_readonly_query(query, max_limit=max_rows)
            if not valid:
                return {'success': False, 'error': msg}

            records = self.execute_query(normalized, parameters=params)
            results = []
            for record in records:
                row = {}
                for key, value in record.items():
                    if hasattr(value, 'labels'):
                        row[key] = {
                            'type': 'node',
                            'id': value.id,
                            'labels': list(value.labels),
                            'properties': dict(value)
                        }
                    elif hasattr(value, 'type'):
                        row[key] = {
                            'type': 'relationship',
                            'id': value.id,
                            'rel_type': value.type,
                            'start_node': value.start_node.id,
                            'end_node': value.end_node.id,
                            'properties': dict(value)
                        }
                    else:
                        row[key] = value
                results.append(row)

            return {'success': True, 'results': results, 'count': len(results), 'query': normalized}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def get_node_count(self):
        """获取节点总数"""
        result = self.execute_query("MATCH (n) RETURN count(n) as count")
        return result[0]['count'] if result else 0

    def get_relationship_count(self):
        """获取关系总数"""
        result = self.execute_query("MATCH ()-[r]->() RETURN count(r) as count")
        return result[0]['count'] if result else 0

    def get_labels(self):
        """获取所有节点标签"""
        result = self.execute_query("CALL db.labels() YIELD label RETURN label")
        return [record['label'] for record in result]

    def get_relationship_types(self):
        """获取所有关系类型"""
        result = self.execute_query("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType")
        return [record['relationshipType'] for record in result]
# 创建全局 Neo4jService 实例
neo4j_service = Neo4jService()

