# 工业大模型知识问答系统

基于大模型的缺陷检测知识问答平台，集成Neo4j图数据库可视化功能。

## 功能特性

- 🏠 **首页**：系统概览和功能入口
- 🔍 **缺陷检测问答**：基于大模型的智能问答系统
- 📊 **图数据库可视化**：使用Neovis.js进行Neo4j数据可视化
- 🔧 **健康检查**：系统和数据库连接状态监控

## 环境要求

- Python 3.8+
- Neo4j 5.x
- JDK 21
- Conda/Miniconda（已配置ddllm环境）

## Conda环境配置

项目使用专门的conda环境 `ddllm`，已预先配置好Python环境和依赖包。

### 激活环境

```bash
conda activate ddllm
```

### 验证环境

```bash
# 检查环境状态
conda info --envs

# 验证Python版本
python --version

# 验证已安装的包
pip list
```

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
│   │   ├── qa.html           # 问答页面
│   │   └── graph_viz.html    # 图可视化页面
│   └── static/               # 静态文件（CSS、JS、图片等）
├── jdk-21.0.9/               # JDK环境
├── neo4j-community-5.26.18/   # Neo4j数据库
├── requirements.txt           # Python依赖
├── start_neo4j.sh            # Neo4j启动脚本
├── stop_neo4j.sh             # Neo4j停止脚本
└── README.md                 # 项目说明
```

## 安装和运行

### 1. 激活Conda环境

```bash
# 激活已创建的ddllm环境
conda activate ddllm
```

### 2. 安装Python依赖

```bash
pip install -r requirements.txt
```

### 3. 启动Neo4j数据库

```bash
# 使用后端目录下的脚本
cd backend
./start_neo4j.sh
```

### 4. 运行Flask应用

```bash
# 方法1：使用启动脚本（推荐）
cd backend
./start_flask.sh

# 方法2：直接运行
cd backend
conda activate ddllm  # 激活conda环境
python app.py
```

### 5. 一键启动（Neo4j + Flask）

```bash
# 在项目根目录运行
./start_system.sh
```

### 6. 系统测试

```bash
# 运行系统测试脚本
./test_system.sh
```

### 4. 访问应用

- **首页**：http://localhost:5000
- **问答系统**：http://localhost:5000/qa
- **图可视化**：http://localhost:5000/graph
- **健康检查**：http://localhost:5000/health

## API接口

### 健康检查
```
GET /health
```

### 图数据查询
```
GET  /api/graph?query=<cypher_query>
POST /api/graph
Body: {"query": "<cypher_query>"}
```

### 数据库统计
```
GET /api/stats
```

### 自定义查询
```
POST /api/query
Body: {"query": "<cypher_query>"}
```

## Neo4j配置

默认配置：
- **服务器地址**：bolt://localhost:7687
- **用户名**：neo4j
- **密码**：detectneo4j

如需修改，请编辑 `backend/services/neo4j_service.py` 中的连接参数。

## 使用说明

### 图可视化功能

1. **执行查询**：在输入框中输入Cypher查询语句，点击"执行查询"
2. **交互操作**：
   - 拖拽节点移动位置
   - 鼠标滚轮缩放视图
   - 点击节点查看详细信息
3. **视图控制**：
   - "重置视图"：适应当前数据
   - "适应屏幕"：缩放到适合屏幕大小

### 示例查询

- `MATCH (n)-[r]->(m) RETURN n,r,m LIMIT 50` - 查看所有节点和关系
- `MATCH (n:Person) RETURN n` - 查看Person类型的节点
- `MATCH (n)-[r:FRIEND]->(m) RETURN n,r,m` - 查看特定关系

### 问答系统

1. 在问答页面输入关于缺陷检测的问题
2. 系统会基于知识库提供智能回答
3. 支持多轮对话和上下文理解

## 开发说明

### 添加新的API接口

1. 在 `backend/routes/api.py` 中添加新的路由函数
2. 如需要，在 `backend/services/` 下添加相应的服务类

### 添加新的页面

1. 在 `frontend/templates/` 下创建新的HTML模板
2. 在 `backend/app.py` 中添加对应的路由
3. 在 `frontend/templates/base.html` 中添加导航菜单项

### 数据库操作

使用 `neo4j_service` 实例进行数据库操作：

```python
from services.neo4j_service import neo4j_service

# 执行查询
results = neo4j_service.execute_query("MATCH (n) RETURN n")

# 获取图数据
graph_data = neo4j_service.get_graph_data()
```

## 注意事项

1. 确保Neo4j服务正在运行
2. 修改Neo4j连接密码为实际密码
3. 如遇到CORS问题，Flask-CORS已配置允许跨域访问
4. 生产环境请修改SECRET_KEY和禁用DEBUG模式
5. 自定义查询接口只允许执行只读查询，不支持写操作