import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CORPUS_DIR = os.path.join(PROJECT_ROOT, "corpus", "cleaned_markdown_corpus")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
VECTOR_DB_PATH = os.path.join(PROJECT_ROOT, "corpus", "vector_db")

MAX_DEBUG_ATTEMPTS = 50


CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KNOWLEDGE_BASE_DIR = os.path.join(PROJECT_ROOT, "knowledge_base")
KB_DB_PATH = os.path.join(KNOWLEDGE_BASE_DIR, "solutions.db")
KB_MD_PATH = os.path.join(KNOWLEDGE_BASE_DIR, "solutions_log.md")