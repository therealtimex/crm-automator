"""
Analytics Data Module for CRM Automator

This module provides data access functions for processing statistics
and suppressed emails, used by the Dashboard and Suppressed tabs.

Functions:
    get_database_stats: Fetch overall processing statistics
    get_suppressed_emails: Query suppressed email list with filters
    get_suppression_stats: Get suppression breakdown by category
"""

import logging
from typing import Dict, List, Any

# Configure logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_LIMIT = 100

# Import PersistenceLayer
try:
    from eml.persistence import PersistenceLayer
except ImportError:
    try:
        from persistence import PersistenceLayer
    except ImportError:
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from persistence import PersistenceLayer

# Shared persistence instance for analytics
db_instance = PersistenceLayer()

def get_database_stats() -> Dict[str, int]:
    """Get statistics from SQLite database using new processing_log table"""
    try:
        stats = db_instance.get_processing_stats()

        # Map to legacy format for dashboard compatibility
        return {
            "total": stats["total"],
            "processed": stats["success"],
            "suppressed": stats["suppressed"],
            "failed": stats["failed"]
        }
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return {"total": 0, "processed": 0, "suppressed": 0, "failed": 0}


def get_suppressed_emails(limit: int = DEFAULT_LIMIT, category: str = None, search: str = None) -> List[Dict]:
    """Get suppressed emails from database using new processing_log table"""
    try:
        # Use persistence layer's method which queries processing_log
        category_filter = category if category and category != "All" else None
        results = db_instance.get_suppressed_emails(
            limit=limit,
            category=category_filter,
            sender=search if search else None
        )

        return results
    except Exception as e:
        logger.error(f"Error getting suppressed emails: {e}")
        return []


def get_suppression_stats() -> Dict[str, Any]:
    """Get suppression statistics"""
    try:
        return db_instance.get_suppression_stats()
    except Exception as e:
        logger.error(f"Error getting suppression stats: {e}")
        return {}
