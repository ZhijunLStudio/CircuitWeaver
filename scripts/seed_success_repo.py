import os
import sys
import shutil
from langchain_community.docstore.document import Document
from langchain_community.vectorstores import FAISS

# --- Setup Project Path ---
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# --- Import Initializers and Tools ---
from src.core.success_code_manager import SuccessCodeManager
from src.tools.documentation_search_tool import init_embedding_model, get_embedding_model
from configs import settings

# --- Configuration ---
# <<< 核心修正 >>>
# 这个脚本现在明确地从 `seed_circuits` 文件夹读取数据，
# 这是由 `generate_ideas.py` 脚本准备好的、结构化的输入。
SEED_DIR = "seed_circuits"

def main():
    print("--- Seeding the Successful Circuits Repository ---")

    if not os.path.exists(SEED_DIR):
        print(f"Error: Seed directory '{SEED_DIR}' not found.")
        print(f"Please run 'python scripts/generate_ideas.py' first to create it from your source files.")
        return

    # --- Safety Check ---
    if os.path.exists(settings.SUCCESS_CODE_REPO_PATH):
        response = input(
            f"WARNING: The production knowledge base '{settings.SUCCESS_CODE_REPO_PATH}' already exists.\n"
            "This script will DELETE it and rebuild it from the seed data in '{SEED_DIR}'.\n"
            "Are you sure you want to continue? (y/N): "
        ).lower()
        if response != 'y':
            print("Operation cancelled.")
            return
        print(f"Removing old repository at '{settings.SUCCESS_CODE_REPO_PATH}'...")
        shutil.rmtree(settings.SUCCESS_CODE_REPO_PATH)

    # --- Initialize Resources ---
    print("Initializing embedding model...")
    try:
        init_embedding_model()
        embedding_model = get_embedding_model()
    except Exception as e:
        print(f"FATAL: Could not initialize embedding model. Error: {e}")
        return
    
    # --- Process Seed Data ---
    print(f"Processing structured examples from '{SEED_DIR}'...")
    
    # Manually create the manager without loading old data
    success_manager = SuccessCodeManager(embedding_model=embedding_model)

    documents_for_faiss = []
    
    example_folders = [f for f in os.listdir(SEED_DIR) if os.path.isdir(os.path.join(SEED_DIR, f))]
    if not example_folders:
        print("No example folders found in the seed directory.")
        return

    for folder in example_folders:
        folder_path = os.path.join(SEED_DIR, folder)
        code_path = os.path.join(folder_path, "source.py")
        idea_path = os.path.join(folder_path, "idea.txt")
        
        if os.path.exists(code_path) and os.path.exists(idea_path):
            print(f"  + Seeding example: {folder}")
            with open(code_path, 'r', encoding='utf-8') as f:
                code = f.read()
            with open(idea_path, 'r', encoding='utf-8') as f:
                idea = f.read().strip()
            
            # Manually perform the actions of `add_success`
            # 1. Save the code file to the final destination
            filename = f"seed_{folder}.py"
            file_path = os.path.join(success_manager.repo_path, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)

            # 2. Write to metadata.jsonl in the final destination
            success_manager._append_to_metadata(filename, idea)

            # 3. Collect document for batch vectorization
            doc = Document(page_content=idea, metadata={"source": filename})
            documents_for_faiss.append(doc)
        else:
            print(f"  - Skipping '{folder}': missing 'source.py' or 'idea.txt'.")
            
    # --- Build Vector DB in One Go (more efficient) ---
    if not documents_for_faiss:
        print("No valid documents collected. Vector DB not built.")
        return
        
    print(f"\nBuilding FAISS vector index for '{settings.SUCCESS_CODE_REPO_PATH}'...")
    vector_store = FAISS.from_documents(documents_for_faiss, embedding_model)
    vector_store.save_local(success_manager.vector_db_path)
    
    print("\n✅ Seeding complete!")
    print(f"'{settings.SUCCESS_CODE_REPO_PATH}' has been successfully built with {len(documents_for_faiss)} examples.")

# We need to add a helper method to SuccessCodeManager for this script
def add_metadata_helper_to_manager():
    """Dynamically adds a helper method to the class for the script."""
    import json
    from datetime import datetime
    
    def _append_to_metadata(self, filename: str, idea: str):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        metadata_entry = {"file_path": filename, "idea": idea, "timestamp": timestamp}
        with open(self.metadata_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(metadata_entry) + '\n')
    
    SuccessCodeManager._append_to_metadata = _append_to_metadata

if __name__ == "__main__":
    add_metadata_helper_to_manager()
    main()