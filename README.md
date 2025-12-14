# 工业缺陷检测智能系统

基于大模型的缺陷检测知识问答平台，集成Neo4j图数据库可视化功能。

## 环境要求

- Python 3.8+
- Neo4j 5.x
- JDK 21

## Conda环境配置

### 创建环境
```bash
conda create -n ddllm python=3.11
```

### 激活环境

```bash
conda activate ddllm
```

### 配置环境
```bash
pip install -r requirements.txt
```

## 环境变量配置

项目使用 `.env` 文件管理敏感信息和配置参数。请在项目根目录创建 `.env` 文件，并配置以下变量：

```bash
# Neo4j 数据库配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password

# Flask 应用配置
SECRET_KEY=your_secret_key_here
FLASK_DEBUG=true

# DeepSeek API 配置
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

### 配置说明

- **NEO4J_URI**: Neo4j 数据库连接地址（默认：bolt://localhost:7687）
- **NEO4J_USER**: Neo4j 用户名（默认：neo4j）
- **NEO4J_PASSWORD**: Neo4j 密码（必须设置）
- **SECRET_KEY**: Flask 应用密钥（生产环境必须修改）
- **FLASK_DEBUG**: 调试模式开关（生产环境设为 false）
- **DEEPSEEK_API_KEY**: DeepSeek 大模型 API 密钥（必须设置）

**注意**：`.env` 文件已添加到 `.gitignore`，不会被提交到版本控制系统。请妥善保管敏感信息。

## 项目结构

```
├── backend/                    # 后端代码
│   ├── app.py                 # Flask应用主文件
│   ├── routes/                # API路由
│   │   ├── __init__.py
│   │   └── api.py            # REST API接口
│   └── services/              # 业务逻辑服务
│       ├── __init__.py
│       └── neo4j_service.py   # Neo4j数据库服务
├── frontend/                   # 前端代码
│   ├── templates/             # HTML模板
│   │   ├── base.html         # 基础模板
│   │   ├── index.html        # 首页
│   │   └── llmkg.html        # 问答 + 图谱页面
│   └── static/               # 静态文件（CSS、JS、图片等）
├── jdk-21.0.9/               # JDK环境
├── neo4j-community-5.26.18/   # Neo4j数据库
├── requirements.txt           # Python依赖
├── start_neo4j.sh            # Neo4j启动脚本
├── stop_neo4j.sh             # Neo4j停止脚本
├── .env                      # 环境变量配置文件（敏感信息）
└── README.md                 # 项目说明
```

## 运行

### 一键启动（Neo4j + Flask）

```bash
# 在项目根目录运行
./start_system.sh
```

### 4. 访问应用

- **首页**：http://localhost:5000

## Neo4j配置

Neo4j 连接参数通过环境变量配置（见“环境变量配置”部分）。

默认配置：
- **服务器地址**：bolt://localhost:7687
- **用户名**：neo4j
- **密码**：通过 `NEO4J_PASSWORD` 环境变量设置

如需修改，请编辑 `.env` 文件中的相应变量。

## 使用说明

### 问答系统（开发中）

1. 在问答页面输入关于缺陷检测的问题
2. 系统会基于知识库提供智能回答
3. 支持多轮对话和上下文理解

### 图可视化功能

1. **执行查询**：在输入框中输入Cypher查询语句，点击"执行查询"
2. **交互操作**：
   - 拖拽节点移动位置
   - 鼠标滚轮缩放视图
   - 点击节点查看详细信息
3. **视图控制**：
   - "重置视图"：适应当前数据
   - "适应屏幕"：缩放到适合屏幕大小

## 注意事项

1. 确保Neo4j服务正在运行
2. 配置 `.env` 文件中的所有必需环境变量
3. 如遇到CORS问题，Flask-CORS已配置允许跨域访问
4. 生产环境请修改SECRET_KEY和禁用DEBUG模式
5. 敏感信息通过环境变量管理，不要硬编码在代码中
5. 自定义查询接口只允许执行只读查询，不支持写操作