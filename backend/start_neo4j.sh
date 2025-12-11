#!/bin/bash

# Neo4j 启动脚本

# 设置 Java 环境变量
export JAVA_HOME="/data/zhanggu/Project/Defect_detection_system/jdk-21.0.9"
export PATH="$JAVA_HOME/bin:$PATH"

# Neo4j 安装目录
NEO4J_HOME="/data/zhanggu/Project/Defect_detection_system/neo4j-community-5.26.18"

# 切换到 Neo4j 目录
cd "$NEO4J_HOME"

# 启动 Neo4j
./bin/neo4j start

# 等待启动
sleep 5