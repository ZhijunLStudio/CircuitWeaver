# src/tools/documentation_search_tool.py
import os
import torch
import threading
from smolagents import Tool
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from configs import models, settings

# --- 全局、进程唯一的资源 ---
embedding_model_instance = None
vector_store_instance = None
# 使用线程锁来确保资源初始化的原子性
resource_lock = threading.Lock()

def get_retriever():
    """
    一个线程安全的函数，用于获取全局唯一的 retriever 实例。
    所有并发的 Agent 都会调用这个函数。
    """
    global embedding_model_instance, vector_store_instance
    
    # 使用双重检查锁定模式，避免每次都获取锁，提高性能
    if vector_store_instance is None:
        with resource_lock:
            # 再次检查，防止在等待锁的过程中其他线程已经初始化完毕
            if vector_store_instance is None:
                print("--- 🧠 Initializing Shared RAG Resources (ONCE) ---")
                
                # 1. 加载 Embedding Model
                print("Lazy loading embedding model for RAG tool...")
                device = 'cuda' if torch.cuda.is_available() else 'cpu'
                print(f"Using device: {device}")
                
                embedding_model_instance = HuggingFaceEmbeddings(
                    model_name=models.EMBEDDING_MODEL,
                    model_kwargs={'device': device},
                    encode_kwargs={'normalize_embeddings': True}
                )
                print("Embedding model loaded.")

                # 2. 加载 Vector Store
                if not os.path.exists(settings.VECTOR_DB_PATH):
                    raise FileNotFoundError(
                        f"Vector DB not found at {settings.VECTOR_DB_PATH}. "
                        "Run 'python scripts/build_vector_db.py' first."
                    )
                print("Lazy loading vector store for RAG tool...")
                vector_store_instance = FAISS.load_local(
                    settings.VECTOR_DB_PATH, 
                    embedding_model_instance, 
                    allow_dangerous_deserialization=True
                )
                print("Vector store loaded.")
                print("--- 🧠 Shared RAG Resources Initialized ---")

    return vector_store_instance.as_retriever(search_kwargs={"k": 3})

class DocumentationSearchTool(Tool):
    name = "documentation_search"
    description = "Searches schemdraw docs for errors or API usage questions."
    inputs = {"query": {"type": "string", "description": "Error message or API question."}}
    output_type = "string"

    def __init__(self):
        super().__init__()
        # 在工具实例化时，不加载任何东西，只是确保函数可用
        self.retriever = None

    def forward(self, query: str) -> str:
        # 只有在第一次调用时，才通过线程安全的函数获取 retriever
        if self.retriever is None:
            self.retriever = get_retriever()
            
        print(f"Executing RAG search with query: '{query}'")
        results = self.retriever.invoke(query)
        
        if not results:
            return "No relevant documentation found."
            
        formatted_results = "\\n\\n---\\n\\n".join(
            [f"Source: {doc.metadata.get('source', 'N/A')}\\n\\n{doc.page_content}" for doc in results]
        )
        print("RAG search complete. Returning snippets to agent.")
        return f"Found relevant documentation snippets:\\n\\n{formatted_results}"