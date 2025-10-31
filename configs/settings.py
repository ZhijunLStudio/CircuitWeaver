import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Directories ---
CORPUS_DIR = os.path.join(PROJECT_ROOT, "corpus", "cleaned_markdown_corpus")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
KNOWLEDGE_BASE_DIR = os.path.join(PROJECT_ROOT, "knowledge_base")

# --- RAG & Knowledge Sources ---
# 1. Official Documentation Vector DB
VECTOR_DB_PATH = os.path.join(PROJECT_ROOT, "corpus", "vector_db")

# 2. NEW: Code-Image Examples Dataset
PROCESSED_CIRCUITS_DIR = os.path.join(PROJECT_ROOT, "corpus", "processed_circuits")
CIRCUIT_EXAMPLES_VECTOR_DB_PATH = os.path.join(PROCESSED_CIRCUITS_DIR, "vector_db")

# 3. Dynamic Success Code Repo
SUCCESS_CODE_REPO_PATH = os.path.join(PROJECT_ROOT, "successful_circuits")

# --- Knowledge Base Paths ---
KB_DB_PATH = os.path.join(KNOWLEDGE_BASE_DIR, "solutions.db")
KB_MD_PATH = os.path.join(KNOWLEDGE_BASE_DIR, "solutions_log.md")

# --- Agent Settings ---
MAX_DEBUG_ATTEMPTS = 20  # Reduced, as initial code should be better
MAX_VISUAL_DEBUG_ATTEMPTS = 20 # For the old visual orchestrator, can be ignored for now
SUCCESS_CODE_RAG_K = 2 # From self-generated successes
EXAMPLE_RAG_K = 3      # NEW: Number of code-image examples to retrieve from docs
MAX_IMAGE_DIMENSION = 512 # NEW: Max width/height for images sent to multimodal model

# --- Sandbox Settings ---
SANDBOX_TIMEOUT = 120

# --- RAG (for documentation) ---
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200