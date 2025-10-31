import os
import torch
from smolagents import Tool
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from configs import models, settings

# --- 全局资源，由 main.py 负责初始化 ---
embedding_model_instance = None
doc_retriever_instance = None

def init_embedding_model():
    """在绝对串行的环境中初始化 Embedding Model。"""
    global embedding_model_instance
    if embedding_model_instance is None:
        print("--- 🧠 Initializing Shared Embedding Model on GPU (ONCE) ---")
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Using device: {device}")
        try:
            embedding_model_instance = HuggingFaceEmbeddings(
                model_name=models.EMBEDDING_MODEL,
                model_kwargs={'device': device, 'trust_remote_code': True},
                encode_kwargs={'normalize_embeddings': True}
            )
            embedding_model_instance.embed_query("warm-up query")
            print("--- 🧠 Shared Embedding Model Initialized and Warmed Up ---")
        except Exception as e:
            print(f"FATAL: Failed to initialize Embedding Model. Error: {e}")
            raise e

# <<< 核心修正：添加 Getter 函数 >>>
def get_embedding_model():
    """安全地获取已初始化的 embedding model 实例。"""
    if embedding_model_instance is None:
        raise RuntimeError("Embedding model not initialized. Call init_embedding_model() from main thread first.")
    return embedding_model_instance

def init_doc_retriever():
    """初始化文档检索器。"""
    global doc_retriever_instance
    if doc_retriever_instance is None:
        print("--- 🧠 Initializing Shared Documentation Vector Store (ONCE) ---")
        # 使用 getter 获取模型，确保它已被初始化
        embedding_model = get_embedding_model() 
        
        if not os.path.exists(settings.VECTOR_DB_PATH):
            raise FileNotFoundError(f"Vector DB not found. Run 'build_vector_db.py' first.")
        
        try:
            doc_vector_store = FAISS.load_local(
                settings.VECTOR_DB_PATH, 
                embedding_model, 
                allow_dangerous_deserialization=True
            )
            doc_retriever_instance = doc_vector_store.as_retriever(search_kwargs={"k": 3})
            print("--- 🧠 Documentation Vector Store Initialized ---")
        except Exception as e:
            print(f"FATAL: Failed to load Documentation Vector Store. Error: {e}")
            raise e

class DocumentationSearchTool(Tool):
    name = "documentation_search"
    description = "Searches schemdraw docs for errors or API usage questions."
    inputs = {"query": {"type": "string", "description": "Error message or API question."}}
    output_type = "string"

    def forward(self, query: str) -> str:
        if doc_retriever_instance is None:
            raise RuntimeError("Doc retriever not initialized. Call initializers from main thread.")
            
        print(f"Executing RAG search on Documentation with query: '{query}'")
        results = doc_retriever_instance.invoke(query)
        if not results: return "No relevant documentation found."
        formatted_results = "\\n\\n---\\n\\n".join([f"Source: {doc.metadata.get('source', 'N/A')}\\n\\n{doc.page_content}" for doc in results])
        print("RAG search complete.")
        return f"Found relevant documentation snippets:\n\n{formatted_results}"