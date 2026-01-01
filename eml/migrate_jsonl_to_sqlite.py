#!/usr/bin/env python3
"""
Migration script: JSONL suppressed emails → SQLite

Migrates existing suppressed_emails.jsonl logs to SQLite database.
This is a one-time migration script for users upgrading to v1.9.4+
"""

import json
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

try:
    from persistence import PersistenceLayer
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from persistence import PersistenceLayer


def migrate_jsonl_to_sqlite(jsonl_path: str, db_path: str = None):
    """
    Migrate JSONL suppressed emails log to SQLite database.

    Args:
        jsonl_path: Path to suppressed_emails.jsonl file
        db_path: Optional custom database path
    """
    jsonl_file = Path(jsonl_path)

    if not jsonl_file.exists():
        print(f"❌ JSONL file not found: {jsonl_path}")
        print("Nothing to migrate.")
        return

    # Initialize persistence layer
    if db_path:
        os.environ["PERSISTENCE_DB_PATH"] = db_path
    persistence = PersistenceLayer()

    print(f"📄 Reading JSONL file: {jsonl_path}")
    print(f"💾 Target database: {persistence.db_path}")

    # Read and migrate entries
    migrated = 0
    errors = 0
    skipped = 0

    with open(jsonl_file, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                skipped += 1
                continue

            try:
                entry = json.loads(line)

                # Extract fields
                timestamp = entry.get("timestamp")
                file_path = entry.get("file_path")
                file_name = entry.get("file_name")
                reason = entry.get("reason")
                category = entry.get("category")
                sender = entry.get("sender")
                recipient = entry.get("recipient")
                subject = entry.get("subject")
                email_date = entry.get("date")  # Note: JSONL uses "date", SQLite uses "email_date"
                message_id = entry.get("message_id")

                # Validate required fields
                if not all([timestamp, file_path, file_name, reason]):
                    print(f"⚠️  Line {line_num}: Missing required fields, skipping")
                    skipped += 1
                    continue

                # Insert into database
                persistence.log_suppressed_email(
                    timestamp=timestamp,
                    file_path=file_path,
                    file_name=file_name,
                    reason=reason,
                    category=category,
                    sender=sender,
                    recipient=recipient,
                    subject=subject,
                    email_date=email_date,
                    message_id=message_id
                )

                migrated += 1

                if migrated % 100 == 0:
                    print(f"✓ Migrated {migrated} entries...")

            except json.JSONDecodeError as e:
                print(f"❌ Line {line_num}: JSON decode error: {e}")
                errors += 1
            except Exception as e:
                print(f"❌ Line {line_num}: Migration error: {e}")
                errors += 1

    print("\n" + "="*60)
    print("MIGRATION SUMMARY")
    print("="*60)
    print(f"✅ Successfully migrated: {migrated}")
    print(f"⚠️  Skipped (empty/invalid): {skipped}")
    print(f"❌ Errors: {errors}")
    print("="*60)

    if migrated > 0:
        print(f"\n✓ Migration complete!")
        print(f"  Database: {persistence.db_path}")
        print(f"\nYou can now:")
        print(f"  - View stats: uv run python eml/eml_automator.py --show-filter-stats <any-path>")
        print(f"  - Query DB: sqlite3 {persistence.db_path} \"SELECT * FROM suppressed_emails LIMIT 10;\"")
        print(f"  - Archive JSONL: mv {jsonl_path} {jsonl_path}.backup")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate JSONL suppressed emails log to SQLite database"
    )
    parser.add_argument(
        "jsonl_path",
        nargs="?",
        default="./logs/suppressed_emails.jsonl",
        help="Path to JSONL file (default: ./logs/suppressed_emails.jsonl)"
    )
    parser.add_argument(
        "--db-path",
        help="Custom database path (default: from PERSISTENCE_DB_PATH env or ./eml_processing.db)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without actually migrating"
    )

    args = parser.parse_args()

    if args.dry_run:
        print("🔍 DRY RUN MODE - No changes will be made")
        jsonl_file = Path(args.jsonl_path)
        if jsonl_file.exists():
            line_count = sum(1 for line in open(jsonl_file) if line.strip())
            print(f"📄 Found {line_count} entries in {args.jsonl_path}")
            print(f"💾 Would migrate to: {args.db_path or 'eml_processing.db'}")
        else:
            print(f"❌ File not found: {args.jsonl_path}")
        return

    migrate_jsonl_to_sqlite(args.jsonl_path, args.db_path)


if __name__ == "__main__":
    main()
