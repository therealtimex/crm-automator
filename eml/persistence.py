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
        os.makedirs(os.path.dirname(self.db_path) or '.', exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Table for tracking processed emails
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_resources (
                resource_id TEXT PRIMARY KEY,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table for suppressed emails (moved from JSONL)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS suppressed_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                reason TEXT NOT NULL,
                category TEXT,
                sender TEXT,
                recipient TEXT,
                subject TEXT,
                email_date TEXT,
                message_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indexes for fast queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_suppressed_timestamp
            ON suppressed_emails(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_suppressed_category
            ON suppressed_emails(category)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_suppressed_reason
            ON suppressed_emails(reason)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_suppressed_sender
            ON suppressed_emails(sender)
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

    def log_suppressed_email(
        self,
        timestamp: str,
        file_path: str,
        file_name: str,
        reason: str,
        category: Optional[str] = None,
        sender: Optional[str] = None,
        recipient: Optional[str] = None,
        subject: Optional[str] = None,
        email_date: Optional[str] = None,
        message_id: Optional[str] = None
    ):
        """Log a suppressed email to the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO suppressed_emails
                (timestamp, file_path, file_name, reason, category, sender, recipient, subject, email_date, message_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (timestamp, file_path, file_name, reason, category, sender, recipient, subject, email_date, message_id))
            conn.commit()
            logger.debug(f"Logged suppressed email: {file_name}")
        except Exception as e:
            logger.error(f"Failed to log suppressed email: {e}")
        finally:
            conn.close()

    def get_suppression_stats(self):
        """Get statistics about suppressed emails."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Total suppressed
            cursor.execute("SELECT COUNT(*) FROM suppressed_emails")
            total = cursor.fetchone()[0]

            # By reason
            cursor.execute("""
                SELECT reason, COUNT(*) as count
                FROM suppressed_emails
                GROUP BY reason
                ORDER BY count DESC
            """)
            by_reason = {row[0]: row[1] for row in cursor.fetchall()}

            # By category
            cursor.execute("""
                SELECT category, COUNT(*) as count
                FROM suppressed_emails
                WHERE category IS NOT NULL
                GROUP BY category
                ORDER BY count DESC
            """)
            by_category = {row[0]: row[1] for row in cursor.fetchall()}

            return {
                "total_suppressed": total,
                "by_reason": by_reason,
                "by_category": by_category,
            }
        except Exception as e:
            logger.error(f"Failed to get suppression stats: {e}")
            return {
                "total_suppressed": 0,
                "by_reason": {},
                "by_category": {},
            }
        finally:
            conn.close()

    def get_suppressed_emails(
        self,
        limit: int = 100,
        offset: int = 0,
        category: Optional[str] = None,
        sender: Optional[str] = None
    ):
        """Get suppressed emails with optional filtering."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        cursor = conn.cursor()

        try:
            query = "SELECT * FROM suppressed_emails WHERE 1=1"
            params = []

            if category:
                query += " AND category = ?"
                params.append(category)

            if sender:
                query += " AND sender LIKE ?"
                params.append(f"%{sender}%")

            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get suppressed emails: {e}")
            return []
        finally:
            conn.close()

    def clear_old_suppressed_emails(self, days: int = 30):
        """Clear suppressed emails older than specified days."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                DELETE FROM suppressed_emails
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            """, (days,))
            deleted = cursor.rowcount
            conn.commit()
            logger.info(f"Cleared {deleted} suppressed emails older than {days} days")
            return deleted
        except Exception as e:
            logger.error(f"Failed to clear old suppressed emails: {e}")
            return 0
        finally:
            conn.close()
