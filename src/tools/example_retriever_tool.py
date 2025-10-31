import os
from langchain_community.vectorstores import FAISS
from configs import settings

# <<< 核心修正：导入 getter 函数，而不是变量 >>>
from src.tools.documentation_search_tool import get_embedding_model

# --- 全局资源，由 main.py 负责初始化 ---
example_retriever_instance = None

def init_example_retriever():
    """初始化图文示例检索器。"""
    global example_retriever_instance
    if example_retriever_instance is None:
        print("--- 🧠 Initializing Shared Circuit Examples Vector Store (ONCE) ---")
        
        # <<< 核心修正：调用 getter 来安全地获取模型 >>>
        embedding_model = get_embedding_model()
            
        if not os.path.exists(settings.CIRCUIT_EXAMPLES_VECTOR_DB_PATH):
            raise FileNotFoundError(
                f"Circuit Examples Vector DB not found at '{settings.CIRCUIT_EXAMPLES_VECTOR_DB_PATH}'. "
                "Run 'scripts/build_circuit_examples_db.py' first."
            )
        
        try:
            example_vector_store = FAISS.load_local(
                settings.CIRCUIT_EXAMPLES_VECTOR_DB_PATH, 
                embedding_model, 
                allow_dangerous_deserialization=True
            )
            example_retriever_instance = example_vector_store.as_retriever(
                search_kwargs={"k": settings.EXAMPLE_RAG_K}
            )
            example_retriever_instance.invoke("test query")
            print("--- 🧠 Circuit Examples Vector Store Initialized ---")
        except Exception as e:
            print(f"FATAL: Failed to load Circuit Examples Vector Store. Error: {e}")
            raise e

class ExampleRetrieverTool:
    def __init__(self):
        if example_retriever_instance is None:
            raise RuntimeError("Example retriever not initialized. Call init_example_retriever() from main thread.")
        self.retriever = example_retriever_instance

    def forward(self, query: str, k: int) -> list[dict]:
        """
        Searches the circuit examples vector store and returns a list of dicts,
        each containing the code and the relative path to its corresponding image.
        """
        print(f"Executing RAG search on Circuit Examples with query: '{query}'")
        self.retriever.search_kwargs['k'] = k
        results = self.retriever.invoke(query)
        
        structured_results = []
        if not results:
            print("No relevant circuit examples found.")
            return []

        for doc in results:
            code = doc.page_content
            image_path = doc.metadata.get('image_path')
            
            if code and image_path:
                structured_results.append({
                    'code': code,
                    'image_path': image_path
                })
            else:
                print(f"Warning: Retrieved document is missing code or image_path metadata. Doc: {doc}")

        print(f"RAG search on examples complete. Found {len(structured_results)} valid pairs.")
        return structured_results