import os
import json
import uuid
from datetime import datetime
from langchain_community.vectorstores import FAISS
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.docstore.document import Document
from configs import settings
import faiss

from src.tools.documentation_search_tool import get_embedding_model

# --- Global Singleton ---
success_code_manager_instance = None

class SuccessCodeManager:
    def __init__(self, embedding_model):
        if embedding_model is None:
            raise ValueError("Embedding model cannot be None.")
            
        self.repo_path = settings.SUCCESS_CODE_REPO_PATH
        self.metadata_path = os.path.join(self.repo_path, "metadata.jsonl")
        self.vector_db_path = os.path.join(self.repo_path, "vector_db")
        os.makedirs(self.repo_path, exist_ok=True)

        self.embedding_model = embedding_model
        self.vector_store = None
        self._load_or_initialize()
    
    def _load_or_initialize(self):
        if os.path.exists(self.vector_db_path) and os.path.exists(self.metadata_path):
            try:
                print("🧠 Loading existing success code vector store...")
                self.vector_store = FAISS.load_local(self.vector_db_path, self.embedding_model, allow_dangerous_deserialization=True)
            except Exception as e:
                print(f"Warning: Could not load success vector store, re-initializing. Error: {e}")
                self._create_new_vector_store()
        else:
            self._create_new_vector_store()
    
    def _create_new_vector_store(self):
        print("🧠 Creating new success code vector store...")
        try:
            embedding_dim = len(self.embedding_model.embed_query("test"))
        except Exception as e:
            print(f"FATAL: Could not determine embedding dimension. Error: {e}")
            raise e
        index = faiss.IndexFlatL2(embedding_dim)
        docstore = InMemoryDocstore({})
        index_to_docstore_id = {}
        self.vector_store = FAISS(embedding_function=self.embedding_model, index=index, docstore=docstore, index_to_docstore_id=index_to_docstore_id)

    def add_success(self, code: str, idea: str):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = uuid.uuid4().hex[:8]
        filename = f"{timestamp}_{unique_id}.py"
        file_path = os.path.join(self.repo_path, filename)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)

        metadata_entry = {"file_path": filename, "idea": idea, "timestamp": timestamp}
        with open(self.metadata_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(metadata_entry) + '\n')

        doc = Document(page_content=idea, metadata={"source": filename})
        self.vector_store.add_documents([doc])
        self.vector_store.save_local(self.vector_db_path)
        print(f"✅ Successfully added new code to success repo: {filename}")

    def retrieve_successes(self, query_idea: str, k: int) -> str:
        """Retrieves relevant examples and formats them as a single string for prompts."""
        if k == 0 or not hasattr(self.vector_store.index, 'ntotal') or self.vector_store.index.ntotal == 0:
            return "No successful examples found in the repository."

        try:
            results = self.vector_store.similarity_search(query_idea, k=k)
            formatted_examples = ""
            for i, doc in enumerate(results):
                filename = doc.metadata.get("source")
                if filename:
                    try:
                        with open(os.path.join(self.repo_path, filename), 'r', encoding='utf-8') as f:
                            code_content = f.read()
                        
                        formatted_examples += f"\n--- Relevant Example #{i+1} (from previous success) ---\n"
                        formatted_examples += f"// This was generated for the concept: \"{doc.page_content}\"\n"
                        formatted_examples += "```python\n"
                        formatted_examples += code_content
                        formatted_examples += "\n```\n"
                    except FileNotFoundError:
                        continue
            
            if not formatted_examples:
                return "No relevant successful examples could be retrieved."
                
            return formatted_examples
        except Exception as e:
            print(f"Error during success code retrieval: {e}")
            return "An error occurred while retrieving successful examples."
    
    # <<< THIS IS THE NEW, MISSING METHOD >>>
    def retrieve_successes_as_docs(self, query_idea: str, k: int) -> list[Document]:
        """Retrieves relevant examples and returns them as a list of Document objects."""
        if k == 0 or not hasattr(self.vector_store.index, 'ntotal') or self.vector_store.index.ntotal == 0:
            return []
        
        try:
            return self.vector_store.similarity_search(query_idea, k=k)
        except Exception as e:
            print(f"Error during success code document retrieval: {e}")
            return []

# --- Singleton Initializer ---
def init_success_code_manager():
    global success_code_manager_instance
    if success_code_manager_instance is None:
        print("--- 🏭 Initializing Shared SuccessCodeManager (ONCE) ---")
        embedding_model = get_embedding_model()
        success_code_manager_instance = SuccessCodeManager(embedding_model=embedding_model)
        print("--- 🏭 Shared SuccessCodeManager Initialized ---")

def get_success_code_manager():
    if success_code_manager_instance is None:
        raise RuntimeError("SuccessCodeManager not initialized. Call init_success_code_manager() from main thread.")
    return success_code_manager_instance