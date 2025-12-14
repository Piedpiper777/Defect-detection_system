from neo4j import GraphDatabase
from dotenv import load_dotenv
import logging
import time
import os

load_dotenv()

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
        self.connect()

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

