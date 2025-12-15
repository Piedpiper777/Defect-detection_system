#!/usr/bin/env python3
import os
import sys
import numpy as np
sys.path.append('backend')

os.environ['SENT_MODEL_PATH'] = '/data/zhanggu/Project/Defect_detection_system/models/Jerry0/text2vec-base-chinese'

def debug_vector_search():
    print("=== 向量搜索调试 ===")

    try:
        from backend.services.llmkg.vector_store import load_index, load_model, search_enhanced

        print("1. 检查索引文件...")
        if not os.path.exists('backend/data/vector_database/index.faiss'):
            print("❌ index.faiss 不存在")
            return
        if not os.path.exists('backend/data/vector_database/metadata.json'):
            print("❌ metadata.json 不存在")
            return
        print("✅ 索引文件存在")

        print("\n2. 加载模型...")
        model = load_model()
        if model is None:
            print("❌ 模型加载失败")
            return
        print("✅ 模型加载成功")

        print("\n3. 测试编码...")
        test_text = "划痕缺陷怎么解决"
        embeddings = model.encode([test_text], batch_size=1)
        print(f"✅ 编码成功，形状: {embeddings.shape if hasattr(embeddings, 'shape') else 'unknown'}")
        print(f"类型: {type(embeddings)}")
        print(f"值示例: {embeddings[0][:5] if hasattr(embeddings, 'shape') and embeddings.shape[0] > 0 else 'N/A'}")

        print("\n4. 加载索引...")
        success = load_index()
        if not success:
            print("❌ 索引加载失败")
            return
        print("✅ 索引加载成功")

        print("\n5. 测试向量搜索...")
        result = search_enhanced(test_text, k=3)
        print(f"搜索结果: {result}")

    except Exception as e:
        print(f"❌ 发生异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_vector_search()
