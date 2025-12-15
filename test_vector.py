#!/usr/bin/env python3
import os
import sys
sys.path.append('backend')

os.environ['SENT_MODEL_PATH'] = '/data/zhanggu/Project/Defect_detection_system/models/Jerry0/text2vec-base-chinese'

from backend.services.llmkg.vector_store import search_enhanced, load_index

def test_vector_search():
    print("Testing vector search...")

    # Load index
    if not load_index():
        print("Failed to load index")
        return

    print("Index loaded successfully")

    # Test search
    from backend.services.llmkg.vector_store import load_model, search
    model = load_model()
    q_emb = model.encode(["划痕缺陷怎么解决"], batch_size=1)
    print(f"Embedding type: {type(q_emb)}")
    print(f"Embedding shape: {q_emb.shape if hasattr(q_emb, 'shape') else 'no shape'}")

    # Test basic search
    try:
        result = search("划痕缺陷怎么解决", k=3)
        print(f"Basic search result: {result}")
    except Exception as e:
        print(f"Basic search failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_vector_search()
