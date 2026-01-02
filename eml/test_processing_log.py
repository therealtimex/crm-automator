#!/usr/bin/env python3
"""
Test script to verify new processing_log functionality
"""

import sys
import os
import sqlite3
from pathlib import Path

def test_processing_log():
    """Test the new processing_log table and methods"""

    print("=" * 60)
    print("Testing Processing Log System")
    print("=" * 60)

    # Import persistence layer
    try:
        from persistence import PersistenceLayer
    except ImportError:
        from eml.persistence import PersistenceLayer

    # Create test database
    import tempfile
    import shutil
    
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_processing.db")
    
    # Override ENV to force usage of temp db
    os.environ["PERSISTENCE_DB_PATH"] = db_path
    
    test_db = PersistenceLayer(db_name="test_processing.db")
    print(f"\n1. Database initialized at: {test_db.db_path}")

    # Verify table exists
    print("\n2. Verifying processing_log table...")
    conn = sqlite3.connect(test_db.db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='processing_log'
    """)
    if cursor.fetchone():
        print("   ✓ processing_log table exists")
    else:
        print("   ✗ processing_log table NOT found")
        return False

    # Check table schema
    cursor.execute("PRAGMA table_info(processing_log)")
    columns = {row[1]: row[2] for row in cursor.fetchall()}

    expected_columns = [
        'id', 'file_path', 'file_name', 'file_hash', 'message_id',
        'sender', 'recipient', 'subject', 'email_date',
        'status', 'processing_started_at', 'processing_completed_at', 'processing_duration_ms',
        'suppression_category', 'suppression_reason',
        'crm_contacts_created', 'crm_companies_created', 'crm_activities_created',
        'crm_deals_created', 'crm_tasks_created',
        'crm_contacts_payload', 'crm_companies_payload', 'crm_activities_payload',
        'crm_deals_payload', 'crm_tasks_payload',
        'crm_error',
        'error_message', 'error_type', 'error_traceback',
        'ai_summary', 'created_at'
    ]

    missing_columns = [col for col in expected_columns if col not in columns]
    if missing_columns:
        print(f"   ✗ Missing columns: {missing_columns}")
        return False
    else:
        print(f"   ✓ All {len(expected_columns)} columns present")

    # Check indexes
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='index' AND tbl_name='processing_log'
    """)
    indexes = [row[0] for row in cursor.fetchall() if not row[0].startswith('sqlite_')]
    print(f"   ✓ {len(indexes)} indexes created: {', '.join(indexes)}")

    conn.close()

    # Test logging methods
    print("\n3. Testing start_processing()...")
    log_id = test_db.start_processing(
        file_path="/test/email.eml",
        message_id="<test@example.com>",
        sender="sender@example.com",
        recipient="recipient@example.com",
        subject="Test Email",
        email_date="2025-01-01"
    )

    if log_id > 0:
        print(f"   ✓ Processing log created with ID: {log_id}")
    else:
        print("   ✗ Failed to create processing log")
        return False

    # Test complete_processing with success
    print("\n4. Testing complete_processing() with success...")
    test_db.complete_processing(
        log_id=log_id,
        status='success',
        processing_duration_ms=1500,
        crm_contacts_created=2,
        crm_companies_created=1,
        crm_activities_created=3,
        crm_contacts_payload='[{"email": "test@example.com"}]'
    )
    print("   ✓ Processing completed successfully")

    # Test suppression logging
    print("\n5. Testing suppression logging...")
    log_id_2 = test_db.start_processing(
        file_path="/test/newsletter.eml",
        message_id="<newsletter@example.com>",
        sender="marketing@example.com",
        subject="Weekly Newsletter"
    )

    test_db.complete_processing(
        log_id=log_id_2,
        status='suppressed',
        processing_duration_ms=500,
        suppression_category='newsletter',
        suppression_reason='Promotional email detected by AI classifier'
    )
    print("   ✓ Suppressed email logged")

    # Test failure logging
    print("\n6. Testing failure logging...")
    log_id_3 = test_db.start_processing(
        file_path="/test/broken.eml",
        message_id="<broken@example.com>",
        sender="test@example.com"
    )

    test_db.complete_processing(
        log_id=log_id_3,
        status='failed',
        processing_duration_ms=100,
        error_message="Failed to parse email",
        error_type="ValueError",
        error_traceback="Traceback: line 1..."
    )
    print("   ✓ Failed processing logged")

    # Test query methods
    print("\n7. Testing query methods...")

    # Get processing stats
    stats = test_db.get_processing_stats()
    print(f"   ✓ Processing stats: {stats}")

    if stats['total'] != 3:
        print(f"   ✗ Expected 3 total, got {stats['total']}")
        return False
    if stats['success'] != 1:
        print(f"   ✗ Expected 1 success, got {stats['success']}")
        return False
    if stats['suppressed'] != 1:
        print(f"   ✗ Expected 1 suppressed, got {stats['suppressed']}")
        return False
    if stats['failed'] != 1:
        print(f"   ✗ Expected 1 failed, got {stats['failed']}")
        return False

    # Get processing history
    history = test_db.get_processing_history(limit=10)
    print(f"   ✓ Processing history: {len(history)} records")

    # Get suppression breakdown
    breakdown = test_db.get_suppression_breakdown()
    print(f"   ✓ Suppression breakdown: {breakdown}")

    # Test is_already_processed
    print("\n8. Testing is_already_processed()...")
    already_processed = test_db.is_already_processed("<test@example.com>")
    if already_processed:
        print("   ✓ Correctly identified already processed email")
    else:
        print("   ✗ Failed to identify processed email")
        return False

    not_processed = test_db.is_already_processed("<new@example.com>")
    if not not_processed:
        print("   ✓ Correctly identified new email")
    else:
        print("   ✗ Incorrectly identified new email as processed")
        return False

    # Test legacy compatibility
    print("\n9. Testing legacy method compatibility...")
    suppressed_emails = test_db.get_suppressed_emails(limit=10)
    if len(suppressed_emails) == 1:
        print(f"   ✓ Legacy get_suppressed_emails() works: {len(suppressed_emails)} results")
    else:
        print(f"   ✗ Expected 1 suppressed email, got {len(suppressed_emails)}")
        return False

    print("\n" + "=" * 60)
    print("✓ All processing log tests passed!")
    print("=" * 60)
    print("\nNew Features Available:")
    print("  • Comprehensive processing logs for all emails")
    print("  • Success/Suppressed/Failed/Skipped status tracking")
    print("  • CRM operation counts (contacts, companies, activities)")
    print("  • Processing duration metrics")
    print("  • Full error tracking with tracebacks")
    print("  • AI analysis summary storage")
    print("   • Advanced analytics queries")
    print()
    
    # Cleanup
    shutil.rmtree(temp_dir)

    return True


if __name__ == "__main__":
    try:
        success = test_processing_log()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
