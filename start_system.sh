#!/bin/bash

# 一键启动脚本 - 启动Neo4j和Flask应用

echo "=== 工业缺陷检测智能系统启动脚本 ==="
echo ""

# 启动Neo4j
echo "启动Neo4j数据库..."

# 加载 .env 中的配置
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

# 设置 Java 环境变量
export JAVA_HOME="${JAVA_HOME:-/data/zhanggu/Project/Defect_detection_system/jdk-21.0.9}"
export PATH="$JAVA_HOME/bin:$PATH"

# Neo4j 安装目录与认证信息
NEO4J_HOME="${NEO4J_HOME:-/data/zhanggu/Project/Defect_detection_system/neo4j-community-5.26.18}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:?请在 .env 中设置 NEO4J_PASSWORD}"

# 使用 backend/scripts 启动 Neo4j（脚本会设置 JAVA_HOME）
bash backend/scripts/start_neo4j.sh

# 返回项目根目录，然后进入backend目录
cd "/data/zhanggu/Project/Defect_detection_system/backend"

# 等待Neo4j启动
echo "等待Neo4j启动..."
sleep 10

# 检查Neo4j是否可用
echo "检查Neo4j连接..."
MAX_WAIT=30
WAIT_COUNT=0

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if "$NEO4J_HOME/bin/neo4j" status | grep -q "Neo4j is running"; then
        echo "✅ Neo4j已准备就绪"
        break
    fi
    echo "等待Neo4j... ($((WAIT_COUNT + 1))/$MAX_WAIT)"
    sleep 2
    WAIT_COUNT=$((WAIT_COUNT + 1))
done

if [ $WAIT_COUNT -eq $MAX_WAIT ]; then
    echo "❌ Neo4j启动超时，请检查日志"
    exit 1
fi

# 使用 cypher-shell 进一步确认 Bolt 服务可用
echo "验证Neo4j Bolt服务..."
BOLT_WAIT=30
BOLT_COUNT=0
while [ $BOLT_COUNT -lt $BOLT_WAIT ]; do
    if "$NEO4J_HOME/bin/cypher-shell" -a "bolt://localhost:7687" -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "RETURN 1" >/dev/null 2>&1; then
        echo "✅ Neo4j Bolt服务已准备就绪"
        break
    fi
    echo "等待Bolt服务... ($((BOLT_COUNT + 1))/$BOLT_WAIT)"
    sleep 2
    BOLT_COUNT=$((BOLT_COUNT + 1))
done

if [ $BOLT_COUNT -eq $BOLT_WAIT ]; then
    echo "❌ Bolt服务验证失败，请检查Neo4j日志"
    exit 1
fi

# 启动Flask应用
echo "启动Flask应用..."
python app.py &
FLASK_PID=$!

echo ""
echo "=== 系统启动完成 ==="
echo "📊 Neo4j Browser: http://localhost:7474"
echo "🏠 首页: http://localhost:5000/"
echo "🔍 问答系统: http://localhost:5000/llmkg"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

# 等待用户中断
trap "echo '正在停止服务...'; kill $FLASK_PID 2>/dev/null; cd backend && ./scripts/stop_neo4j.sh; exit 0" INT

# 保持脚本运行
wait $FLASK_PID