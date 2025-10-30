# configs/settings.py
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Directories ---
CORPUS_DIR = os.path.join(PROJECT_ROOT, "corpus", "cleaned_markdown_corpus")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
VECTOR_DB_PATH = os.path.join(PROJECT_ROOT, "corpus", "vector_db")
KNOWLEDGE_BASE_DIR = os.path.join(PROJECT_ROOT, "knowledge_base")
SUCCESS_CODE_REPO_PATH = os.path.join(PROJECT_ROOT, "successful_circuits") # V3 Feature

# --- Knowledge Base Paths ---
KB_DB_PATH = os.path.join(KNOWLEDGE_BASE_DIR, "solutions.db")
KB_MD_PATH = os.path.join(KNOWLEDGE_BASE_DIR, "solutions_log.md")

# --- Agent Settings ---
MAX_DEBUG_ATTEMPTS = 20
SUCCESS_CODE_RAG_K = 3 # V3 Feature: Number of successful examples to retrieve

# --- RAG ---
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200