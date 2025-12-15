from flask import Flask, render_template, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import logging
import os
from routes.llmkg.llm_api import llm_bp
from routes.llmkg.kg_api import kg_bp
from services.llmkg.kg_service import neo4j_service

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 加载 .env 配置
load_dotenv()

# 设置默认的SENT_MODEL_PATH环境变量
if not os.getenv('SENT_MODEL_PATH'):
    default_model_path = os.path.join(os.path.dirname(__file__), '..', 'models', 'Jerry0', 'text2vec-base-chinese')
    os.environ['SENT_MODEL_PATH'] = default_model_path
    logger.info(f"设置默认SENT_MODEL_PATH: {default_model_path}")

def create_app():
    """创建Flask应用"""
    app = Flask(__name__,
                template_folder='../frontend/templates',
                static_folder='../frontend/static')

    # 配置
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'

    # 启用CORS
    CORS(app)

    # 注册蓝图
    app.register_blueprint(llm_bp, url_prefix='/api/llm')
    app.register_blueprint(kg_bp, url_prefix='/api/kg')

    # neo4j前端配置
    def _neo4j_frontend_config():
        return {
            "serverUrl": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            "serverUser": os.getenv("NEO4J_USER", "neo4j"),
            "serverPassword": os.getenv("NEO4J_PASSWORD", "neo4j")
        }

    @app.route('/')
    def index():
        """首页"""
        return render_template('index.html')

    @app.route('/llmkg')
    def llmkg():
        """问答+图谱页面"""
        return render_template('llmkg/llmkg.html', neo4j_config=_neo4j_frontend_config())

    # 错误处理
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': '页面不存在'}), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': '服务器内部错误'}), 500

    # 应用启动时的初始化
    @app.before_request
    def initialize():
        if not hasattr(app, '_initialized'):
            logger.info("初始化应用...")
            try:
                # 测试Neo4j连接
                node_count = neo4j_service.get_node_count()
                logger.info(f"Neo4j连接成功，节点数量: {node_count}")
                app._initialized = True
            except Exception as e:
                logger.error(f"Neo4j连接失败: {str(e)}")
                app._initialized = True  # 避免重复尝试

    return app

# 创建应用实例
app = create_app()

if __name__ == '__main__':
    # 确保模板目录存在
    template_dir = os.path.join(os.path.dirname(__file__), '../frontend/templates')
    if not os.path.exists(template_dir):
        logger.warning(f"模板目录不存在: {template_dir}")

    logger.info("启动Flask应用...")
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True
    )
