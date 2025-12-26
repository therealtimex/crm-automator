import os
import sqlite3
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class PersistenceLayer:
    def __init__(self, db_name: str = "processed_resources.db"):
        # Allow ENV to override db path for production
        env_db_path = os.environ.get("PERSISTENCE_DB_PATH")
        if env_db_path:
            self.db_path = env_db_path
        else:
            # Sandbox safety: Default to current working directory instead of package dir
            self.db_path = os.path.join(os.getcwd(), "eml_processing.db")
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_resources (
                resource_id TEXT PRIMARY KEY,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def is_already_processed(self, resource_id: str) -> bool:
        if not resource_id:
            return False
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM processed_resources WHERE resource_id = ?", (resource_id,))
            exists = cursor.fetchone() is not None
            return exists
        except Exception as e:
            logger.error(f"Persistence check failed: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()

    def mark_as_processed(self, resource_id: str):
        if not resource_id:
            return
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT OR IGNORE INTO processed_resources (resource_id) VALUES (?)", (resource_id,))
            conn.commit()
        except Exception as e:
            print(f"Error marking as processed: {e}")
        finally:
            conn.close()
