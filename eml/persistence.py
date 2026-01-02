import os
import sqlite3
import logging
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class PersistenceLayer:
    def __init__(self, db_name: str = "eml_processing.db"):
        # Allow ENV to override db path for production
        env_db_path = os.environ.get("PERSISTENCE_DB_PATH")
        if env_db_path:
            self.db_path = env_db_path
        else:
            # Default to current working directory
            self.db_path = os.path.join(os.getcwd(), db_name)
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path) or '.', exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # ===== Main Processing Log Table =====
        # This table captures EVERY processing attempt with full details
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                -- File/Email Identity
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_hash TEXT,
                message_id TEXT,

                -- Email Metadata
                sender TEXT,
                recipient TEXT,
                subject TEXT,
                email_date TEXT,

                -- Processing Outcome
                status TEXT NOT NULL CHECK(status IN ('success', 'suppressed', 'failed', 'skipped')),
                processing_started_at TEXT NOT NULL,
                processing_completed_at TEXT,
                processing_duration_ms INTEGER,

                -- Suppression Info (if status='suppressed')
                suppression_category TEXT,
                suppression_reason TEXT,

                -- CRM Integration (if status='success')
                crm_contacts_created INTEGER DEFAULT 0,
                crm_companies_created INTEGER DEFAULT 0,
                crm_activities_created INTEGER DEFAULT 0,
                crm_deals_created INTEGER DEFAULT 0,
                crm_tasks_created INTEGER DEFAULT 0,
                crm_error TEXT,

                -- CRM Payloads (JSON strings)
                crm_contacts_payload TEXT,
                crm_companies_payload TEXT,
                crm_activities_payload TEXT,
                crm_deals_payload TEXT,
                crm_tasks_payload TEXT,

                -- Error Info (if status='failed')
                error_message TEXT,
                error_type TEXT,
                error_traceback TEXT,

                -- AI Analysis Summary (JSON blob)
                ai_summary TEXT,

                -- Metadata
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Indexes for fast queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON processing_log(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_message_id ON processing_log(message_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sender ON processing_log(sender)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_processing_date ON processing_log(processing_started_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON processing_log(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_hash ON processing_log(file_hash)")

        # ===== Schema Migrations =====
        # Add CRM payload columns if they don't exist (for existing databases)
        cursor.execute("PRAGMA table_info(processing_log)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        migrations = [
            ("crm_deals_created", "ALTER TABLE processing_log ADD COLUMN crm_deals_created INTEGER DEFAULT 0"),
            ("crm_tasks_created", "ALTER TABLE processing_log ADD COLUMN crm_tasks_created INTEGER DEFAULT 0"),
            ("crm_contacts_payload", "ALTER TABLE processing_log ADD COLUMN crm_contacts_payload TEXT"),
            ("crm_companies_payload", "ALTER TABLE processing_log ADD COLUMN crm_companies_payload TEXT"),
            ("crm_activities_payload", "ALTER TABLE processing_log ADD COLUMN crm_activities_payload TEXT"),
            ("crm_deals_payload", "ALTER TABLE processing_log ADD COLUMN crm_deals_payload TEXT"),
            ("crm_tasks_payload", "ALTER TABLE processing_log ADD COLUMN crm_tasks_payload TEXT"),
        ]

        for column_name, migration_sql in migrations:
            if column_name not in existing_columns:
                cursor.execute(migration_sql)

        # ===== Legacy Tables (for backward compatibility during transition) =====
        # These can be removed after confirming no dependencies
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_resources (
                resource_id TEXT PRIMARY KEY,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

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

        conn.commit()
        conn.close()

    # ========== NEW: Comprehensive Processing Log Methods ==========

    def start_processing(
        self,
        file_path: str,
        message_id: Optional[str] = None,
        sender: Optional[str] = None,
        recipient: Optional[str] = None,
        subject: Optional[str] = None,
        email_date: Optional[str] = None,
        file_hash: Optional[str] = None
    ) -> int:
        """
        Start a processing log entry and return the log ID.
        Call this at the beginning of processing.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            file_name = Path(file_path).name
            cursor.execute("""
                INSERT INTO processing_log
                (file_path, file_name, file_hash, message_id, sender, recipient, subject, email_date,
                 status, processing_started_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'skipped', ?)
            """, (
                file_path,
                file_name,
                file_hash,
                message_id,
                sender,
                recipient,
                subject,
                email_date,
                datetime.utcnow().isoformat()
            ))
            conn.commit()
            log_id = cursor.lastrowid
            logger.debug(f"Started processing log entry: {log_id}")
            return log_id
        except Exception as e:
            logger.error(f"Failed to start processing log: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()

    def complete_processing(
        self,
        log_id: int,
        status: str,
        processing_duration_ms: Optional[int] = None,
        # Suppression fields
        suppression_category: Optional[str] = None,
        suppression_reason: Optional[str] = None,
        # CRM fields
        crm_contacts_created: int = 0,
        crm_companies_created: int = 0,
        crm_activities_created: int = 0,
        crm_deals_created: int = 0,
        crm_tasks_created: int = 0,
        crm_error: Optional[str] = None,
        # CRM Payloads
        crm_contacts_payload: Optional[str] = None,
        crm_companies_payload: Optional[str] = None,
        crm_activities_payload: Optional[str] = None,
        crm_deals_payload: Optional[str] = None,
        crm_tasks_payload: Optional[str] = None,
        # Error fields
        error_message: Optional[str] = None,
        error_type: Optional[str] = None,
        error_traceback: Optional[str] = None,
        # AI summary
        ai_summary: Optional[Dict[str, Any]] = None
    ):
        """
        Complete a processing log entry with outcome details.
        Call this at the end of processing (success or failure).
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Serialize AI summary if provided
            ai_summary_json = json.dumps(ai_summary) if ai_summary else None

            cursor.execute("""
                UPDATE processing_log
                SET status = ?,
                    processing_completed_at = ?,
                    processing_duration_ms = ?,
                    suppression_category = ?,
                    suppression_reason = ?,
                    crm_contacts_created = ?,
                    crm_companies_created = ?,
                    crm_activities_created = ?,
                    crm_deals_created = ?,
                    crm_tasks_created = ?,
                    crm_error = ?,
                    crm_contacts_payload = ?,
                    crm_companies_payload = ?,
                    crm_activities_payload = ?,
                    crm_deals_payload = ?,
                    crm_tasks_payload = ?,
                    error_message = ?,
                    error_type = ?,
                    error_traceback = ?,
                    ai_summary = ?
                WHERE id = ?
            """, (
                status,
                datetime.utcnow().isoformat(),
                processing_duration_ms,
                suppression_category,
                suppression_reason,
                crm_contacts_created,
                crm_companies_created,
                crm_activities_created,
                crm_deals_created,
                crm_tasks_created,
                crm_error,
                crm_contacts_payload,
                crm_companies_payload,
                crm_activities_payload,
                crm_deals_payload,
                crm_tasks_payload,
                error_message,
                error_type,
                error_traceback,
                ai_summary_json,
                log_id
            ))
            conn.commit()
            logger.debug(f"Completed processing log entry: {log_id} with status: {status}")
        except Exception as e:
            logger.error(f"Failed to complete processing log: {e}")
            conn.rollback()
        finally:
            conn.close()

    def is_already_processed(self, resource_id: str) -> bool:
        """
        Check if a resource has been successfully processed before.
        Uses processing_log table for accurate checks.
        """
        if not resource_id:
            return False
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # Check if we have a successful processing record
            cursor.execute("""
                SELECT 1 FROM processing_log
                WHERE message_id = ? AND status = 'success'
                LIMIT 1
            """, (resource_id,))
            exists = cursor.fetchone() is not None
            return exists
        except Exception as e:
            logger.error(f"Persistence check failed: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()

    # ========== Query Methods for Analytics ==========

    def get_processing_stats(self, days: Optional[int] = None) -> Dict[str, int]:
        """Get overall processing statistics, optionally filtered by days."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            where_clause = ""
            params = []
            if days:
                where_clause = "WHERE processing_started_at >= datetime('now', '-' || ? || ' days')"
                params.append(days)

            # Get counts by status
            cursor.execute(f"""
                SELECT status, COUNT(*) as count
                FROM processing_log
                {where_clause}
                GROUP BY status
            """, params)

            stats = {
                "total": 0,
                "success": 0,
                "suppressed": 0,
                "failed": 0,
                "skipped": 0
            }

            for status, count in cursor.fetchall():
                stats[status] = count
                stats["total"] += count

            return stats
        except Exception as e:
            logger.error(f"Failed to get processing stats: {e}")
            return {"total": 0, "success": 0, "suppressed": 0, "failed": 0, "skipped": 0}
        finally:
            conn.close()

    def get_processing_history(
        self,
        limit: int = 100,
        offset: int = 0,
        status: Optional[str] = None,
        sender: Optional[str] = None,
        days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get processing history with optional filtering."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            query = "SELECT * FROM processing_log WHERE 1=1"
            params = []

            if status:
                query += " AND status = ?"
                params.append(status)

            if sender:
                query += " AND sender LIKE ?"
                params.append(f"%{sender}%")

            if days:
                query += " AND processing_started_at >= datetime('now', '-' || ? || ' days')"
                params.append(days)

            query += " ORDER BY processing_started_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get processing history: {e}")
            return []
        finally:
            conn.close()

    def get_suppression_breakdown(self) -> Dict[str, int]:
        """Get suppression counts by category."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT suppression_category, COUNT(*) as count
                FROM processing_log
                WHERE status = 'suppressed' AND suppression_category IS NOT NULL
                GROUP BY suppression_category
                ORDER BY count DESC
            """)
            return {row[0]: row[1] for row in cursor.fetchall()}
        except Exception as e:
            logger.error(f"Failed to get suppression breakdown: {e}")
            return {}
        finally:
            conn.close()

    def get_timeline_data(self, days: int = 30) -> Dict[str, Any]:
        """Get daily processing timeline data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT
                    DATE(processing_started_at) as date,
                    status,
                    COUNT(*) as count
                FROM processing_log
                WHERE processing_started_at >= datetime('now', '-' || ? || ' days')
                GROUP BY DATE(processing_started_at), status
                ORDER BY date ASC
            """, (days,))

            # Organize by date
            timeline = {}
            for date, status, count in cursor.fetchall():
                if date not in timeline:
                    timeline[date] = {"success": 0, "suppressed": 0, "failed": 0, "skipped": 0}
                timeline[date][status] = count

            return timeline
        except Exception as e:
            logger.error(f"Failed to get timeline data: {e}")
            return {}
        finally:
            conn.close()

    def get_top_senders(self, limit: int = 10) -> List[tuple]:
        """Get top senders by email count."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT sender, COUNT(*) as count
                FROM processing_log
                WHERE sender IS NOT NULL
                GROUP BY sender
                ORDER BY count DESC
                LIMIT ?
            """, (limit,))
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"Failed to get top senders: {e}")
            return []
        finally:
            conn.close()

    def get_average_processing_time(self) -> Optional[float]:
        """Get average processing time in milliseconds."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT AVG(processing_duration_ms)
                FROM processing_log
                WHERE processing_duration_ms IS NOT NULL AND status = 'success'
            """)
            result = cursor.fetchone()
            return result[0] if result and result[0] else None
        except Exception as e:
            logger.error(f"Failed to get average processing time: {e}")
            return None
        finally:
            conn.close()

    # ========== Legacy Methods (for backward compatibility) ==========

    def mark_as_processed(self, resource_id: str):
        """
        Legacy method - now a no-op since we use processing_log.
        Kept for backward compatibility during transition.
        """
        logger.debug(f"mark_as_processed called (legacy method, using processing_log instead)")
        pass

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
        """
        Legacy method for suppressed email logging.
        Now redirects to processing_log.
        """
        logger.debug(f"log_suppressed_email called (legacy method)")
        # This is now handled by complete_processing() with status='suppressed'
        pass

    def get_suppression_stats(self):
        """Legacy method for suppression stats."""
        try:
            breakdown = self.get_suppression_breakdown()
            total = sum(breakdown.values())

            return {
                "total_suppressed": total,
                "by_category": breakdown,
                "by_reason": {}  # Could add if needed
            }
        except Exception as e:
            logger.error(f"Failed to get suppression stats: {e}")
            return {
                "total_suppressed": 0,
                "by_category": {},
                "by_reason": {}
            }

    def get_suppressed_emails(
        self,
        limit: int = 100,
        offset: int = 0,
        category: Optional[str] = None,
        sender: Optional[str] = None
    ):
        """Legacy method - now queries processing_log."""
        try:
            filters = {"status": "suppressed"}
            if category:
                # Need custom query for suppression_category
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                query = "SELECT * FROM processing_log WHERE status = 'suppressed'"
                params = []

                if category:
                    query += " AND suppression_category = ?"
                    params.append(category)

                if sender:
                    query += " AND sender LIKE ?"
                    params.append(f"%{sender}%")

                query += " ORDER BY processing_started_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor.execute(query, params)
                results = [dict(row) for row in cursor.fetchall()]
                conn.close()

                # Map to legacy format
                return [{
                    "id": r["id"],
                    "timestamp": r["processing_started_at"],
                    "file_path": r["file_path"],
                    "file_name": r["file_name"],
                    "reason": r["suppression_reason"],
                    "category": r["suppression_category"],
                    "sender": r["sender"],
                    "recipient": r["recipient"],
                    "subject": r["subject"],
                    "email_date": r["email_date"],
                    "message_id": r["message_id"]
                } for r in results]
            else:
                return self.get_processing_history(limit=limit, offset=offset, status="suppressed", sender=sender)
        except Exception as e:
            logger.error(f"Failed to get suppressed emails: {e}")
            return []

    def clear_old_suppressed_emails(self, days: int = 30):
        """Legacy method - now clears from processing_log."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute("""
                DELETE FROM processing_log
                WHERE status = 'suppressed'
                AND processing_started_at < datetime('now', '-' || ? || ' days')
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
