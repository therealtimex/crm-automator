"""Logging utilities for suppressed emails using SQLite."""

import os
import logging
from datetime import datetime
from pathlib import Path
from email.message import Message
from typing import Optional

logger = logging.getLogger(__name__)


def log_suppressed_email(
    file_path: Path,
    email_msg: Message,
    reason: str,
    category: Optional[str] = None,
    persistence_layer=None
) -> None:
    """
    Log suppressed email to SQLite database.

    Args:
        file_path: Path to the EML file
        email_msg: Email message object
        reason: Reason for suppression (e.g., "heuristic:promotional")
        category: Optional email category
        persistence_layer: PersistenceLayer instance (if None, creates new one)
    """
    # Check if logging is enabled
    log_enabled = os.environ.get("LOG_SUPPRESSED", "true").lower() in ["true", "1", "yes"]
    if not log_enabled:
        return

    # Get or create persistence layer
    if persistence_layer is None:
        try:
            from eml.persistence import PersistenceLayer
        except ImportError:
            from persistence import PersistenceLayer
        persistence_layer = PersistenceLayer()

    # Log to database
    try:
        persistence_layer.log_suppressed_email(
            timestamp=datetime.now().isoformat(),
            file_path=str(file_path),
            file_name=file_path.name,
            reason=reason,
            category=category,
            sender=email_msg.get('From', 'Unknown'),
            recipient=email_msg.get('To', 'Unknown'),
            subject=email_msg.get('Subject', 'No Subject'),
            email_date=email_msg.get('Date', 'Unknown'),
            message_id=email_msg.get('Message-ID', 'Unknown'),
        )
    except Exception as e:
        logger.error(f"Failed to log suppressed email: {e}")


def get_suppression_stats(persistence_layer=None) -> dict:
    """
    Get statistics from suppressed emails database.

    Args:
        persistence_layer: PersistenceLayer instance (if None, creates new one)

    Returns:
        Dictionary with statistics
    """
    # Get or create persistence layer
    if persistence_layer is None:
        try:
            from eml.persistence import PersistenceLayer
        except ImportError:
            from persistence import PersistenceLayer
        persistence_layer = PersistenceLayer()

    try:
        return persistence_layer.get_suppression_stats()
    except Exception as e:
        logger.error(f"Failed to get suppression stats: {e}")
        return {
            "total_suppressed": 0,
            "by_reason": {},
            "by_category": {},
        }


def print_suppression_report(persistence_layer=None) -> None:
    """
    Print a formatted report of suppressed emails from database.

    Args:
        persistence_layer: PersistenceLayer instance (if None, creates new one)
    """
    stats = get_suppression_stats(persistence_layer)

    print("\n" + "="*60)
    print("SUPPRESSED EMAILS REPORT")
    print("="*60)
    print(f"\nTotal Suppressed: {stats['total_suppressed']}")

    if stats['by_reason']:
        print("\nBy Reason:")
        for reason, count in sorted(
            stats['by_reason'].items(),
            key=lambda x: x[1],
            reverse=True
        ):
            print(f"  {reason}: {count}")

    if stats['by_category']:
        print("\nBy Category:")
        for category, count in sorted(
            stats['by_category'].items(),
            key=lambda x: x[1],
            reverse=True
        ):
            if category and category != "unknown":
                print(f"  {category}: {count}")

    print("="*60 + "\n")


def get_suppressed_emails(
    limit: int = 100,
    offset: int = 0,
    category: Optional[str] = None,
    sender: Optional[str] = None,
    persistence_layer=None
):
    """
    Get suppressed emails from database with optional filtering.

    Args:
        limit: Maximum number of results
        offset: Offset for pagination
        category: Filter by category
        sender: Filter by sender (partial match)
        persistence_layer: PersistenceLayer instance (if None, creates new one)

    Returns:
        List of suppressed email dictionaries
    """
    # Get or create persistence layer
    if persistence_layer is None:
        try:
            from eml.persistence import PersistenceLayer
        except ImportError:
            from persistence import PersistenceLayer
        persistence_layer = PersistenceLayer()

    try:
        return persistence_layer.get_suppressed_emails(
            limit=limit,
            offset=offset,
            category=category,
            sender=sender
        )
    except Exception as e:
        logger.error(f"Failed to get suppressed emails: {e}")
        return []


def clear_old_suppressed_emails(days: int = 30, persistence_layer=None) -> int:
    """
    Clear suppressed emails older than specified days.

    Args:
        days: Number of days to keep
        persistence_layer: PersistenceLayer instance (if None, creates new one)

    Returns:
        Number of emails deleted
    """
    # Get or create persistence layer
    if persistence_layer is None:
        try:
            from eml.persistence import PersistenceLayer
        except ImportError:
            from persistence import PersistenceLayer
        persistence_layer = PersistenceLayer()

    try:
        return persistence_layer.clear_old_suppressed_emails(days)
    except Exception as e:
        logger.error(f"Failed to clear old suppressed emails: {e}")
        return 0
