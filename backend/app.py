from flask import Flask, render_template, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import logging
import os
from routes.api import api_bp
from services.neo4j_service import neo4j_service

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 加载 .env 配置
load_dotenv()

def create_app():
    """创建Flask应用"""
    app = Flask(__name__,
                template_folder='../frontend/templates',
                static_folder='../frontend/static')

    # 配置
    app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'
    app.config['DEBUG'] = True

    # 启用CORS
    CORS(app)

    # 注册蓝图
    app.register_blueprint(api_bp, url_prefix='/api')

    # 路由
    @app.route('/')
    def index():
        """首页"""
        return render_template('index.html')

    @app.route('/qa')
    def qa():
        """问答+图谱页面"""
        return render_template('qa.html')

    @app.route('/graph')
    def graph():
        """兼容旧链接，跳转到合并后的页面"""
        return render_template('qa.html')

    @app.route('/health')
    def health():
        """健康检查"""
        try:
            node_count = neo4j_service.get_node_count()
            return jsonify({
                'status': 'healthy',
                'neo4j_connected': True,
                'node_count': node_count,
                'message': '系统运行正常'
            })
        except Exception as e:
            return jsonify({
                'status': 'unhealthy',
                'neo4j_connected': False,
                'error': str(e),
                'message': '系统异常'
            }), 500

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
