import os
import sys
import json
import torch
from tqdm import tqdm
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.docstore.document import Document

# Add project root to path to import configs
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from configs import models, settings

# ==================== 新增配置 ====================
# 你可以根据你的显存大小调整这个值。对于24G显存，16或32是比较安全的值。
BATCH_SIZE = 4
# ================================================

def main():
    print("--- Building Vector DB for Code-Image Circuit Examples ---")
    manifest_path = os.path.join(settings.PROCESSED_CIRCUITS_DIR, 'manifest.json')
    if not os.path.exists(manifest_path):
        print(f"Error: manifest.json not found in {settings.PROCESSED_CIRCUITS_DIR}")
        return

    print("Loading manifest and filtering for code-image pairs...")
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    documents = []
    for item in manifest:
        if item.get('type') == 'pair' and item.get('code_path') and item.get('image_path'):
            code_path = os.path.join(settings.PROCESSED_CIRCUITS_DIR, item['code_path'])
            try:
                with open(code_path, 'r', encoding='utf-8') as f_code:
                    code_content = f_code.read()
                
                doc = Document(
                    page_content=code_content,
                    metadata={
                        'source_id': item['id'],
                        'image_path': item['image_path']
                    }
                )
                documents.append(doc)
            except FileNotFoundError:
                print(f"Warning: Code file not found for pair {item['id']}: {code_path}")
            except Exception as e:
                print(f"Error processing pair {item['id']}: {e}")

    if not documents:
        print("Error: No valid code-image pairs found to index.")
        return
    print(f"Found {len(documents)} valid code-image pairs to index.")

    print(f"Loading embedding model: {models.EMBEDDING_MODEL}")
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Using device: {device}")
    
    embedding_model = HuggingFaceEmbeddings(
        model_name=models.EMBEDDING_MODEL,
        model_kwargs={'device': device, 'trust_remote_code': True},
        encode_kwargs={'normalize_embeddings': True}
    )
    print("Embedding model loaded successfully.")

    # ==================== 核心逻辑修正 ====================
    # 不再使用 FAISS.from_documents 一次性加载所有文档
    
    print(f"Processing documents in batches of {BATCH_SIZE}...")
    
    # 步骤 1: 用第一个批次来初始化向量数据库
    first_batch = documents[:BATCH_SIZE]
    vector_store = FAISS.from_documents(first_batch, embedding_model)
    print(f"Initialized vector store with the first {len(first_batch)} documents.")

    # 步骤 2: 循环处理剩余的批次，并添加到已有的数据库中
    remaining_docs = documents[BATCH_SIZE:]
    for i in tqdm(range(0, len(remaining_docs), BATCH_SIZE), desc="Adding document batches"):
        batch = remaining_docs[i:i + BATCH_SIZE]
        if batch:
            vector_store.add_documents(batch)
    # ========================================================
    
    vector_store.save_local(settings.CIRCUIT_EXAMPLES_VECTOR_DB_PATH)
    print(f"\n✅ Circuit Examples Vector DB built and saved to: {settings.CIRCUIT_EXAMPLES_VECTOR_DB_PATH}")

if __name__ == "__main__":
    # 建议在运行前清理一下CUDA缓存
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    main()