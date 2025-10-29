# src/db/knowledge_base.py
import sqlite3
import threading
import os
from datetime import datetime
from configs import settings

class KnowledgeBaseManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(KnowledgeBaseManager, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path=settings.KB_DB_PATH, md_path=settings.KB_MD_PATH):
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            self.db_path = db_path
            self.md_path = md_path
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self._create_table()
            self._initialized = True

    def _create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS solutions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_pattern TEXT NOT NULL UNIQUE,
                solution_summary TEXT NOT NULL,
                timestamp DATETIME NOT NULL
            )
        ''')
        self.conn.commit()

    def add_solution(self, error_pattern: str, solution_summary: str):
        with self._lock:
            try:
                timestamp = datetime.now()
                cursor = self.conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO solutions (error_pattern, solution_summary, timestamp) VALUES (?, ?, ?)",
                    (error_pattern, solution_summary, timestamp)
                )
                self.conn.commit()
                print(f"🧠 New knowledge added to DB: '{error_pattern}'")
                self._append_to_markdown(error_pattern, solution_summary, timestamp)
            except sqlite3.Error as e:
                print(f"Error adding solution to DB: {e}")

    def _append_to_markdown(self, error_pattern: str, solution_summary: str, timestamp: datetime):
        with open(self.md_path, 'a', encoding='utf-8') as f:
            f.write(f"\n---\n\n")
            f.write(f"**🗓️ Timestamp:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**🚫 Error Pattern:**\n```\n{error_pattern}\n```\n\n")
            f.write(f"**💡 Solution:**\n```\n{solution_summary}\n```\n\n")

    def get_relevant_solutions(self, error_message: str, k: int = 2) -> str:
        with self._lock:
            try:
                cursor = self.conn.cursor()
                # A simple LIKE query; for production, consider full-text search or embeddings
                cursor.execute("SELECT solution_summary FROM solutions")
                all_solutions = cursor.fetchall()

                # In-memory simple search for demonstration.
                # A more robust solution would be to use SQLite's FTS5 or another search mechanism.
                # For now, we'll find any solution whose error pattern is a substring of the new error.
                found_solutions = []
                for row in all_solutions:
                    error_pattern = row[0]
                    # This is a placeholder for a real search algorithm.
                    # Let's just return the latest k solutions for now to simulate.
                    pass # We'll implement a better search later.

                # Let's do a simple retrieval of the latest k solutions as a starting point.
                cursor.execute("SELECT solution_summary FROM solutions ORDER BY timestamp DESC LIMIT ?", (k,))
                results = cursor.fetchall()
                
                if not results:
                    return ""
                
                formatted_results = "\n\n".join([f"- {row[0]}" for row in results])
                return f"Here are some potentially related solutions from past fixes:\n{formatted_results}"
            except sqlite3.Error as e:
                print(f"Error retrieving solutions from DB: {e}")
                return ""

# Need to add these paths to configs/settings.py
# KB_DB_PATH = os.path.join(PROJECT_ROOT, "knowledge_base", "solutions.db")
# KB_MD_PATH = os.path.join(PROJECT_ROOT, "knowledge_base", "solutions_log.md")