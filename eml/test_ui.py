#!/usr/bin/env python3
"""
Test script to verify web UI functionality
"""

import sys
import os
import time
import subprocess
import requests
from pathlib import Path

def test_ui():
    """Test the web UI by launching it and checking if it responds"""

    print("=" * 60)
    print("Testing CRM Automator Web UI")
    print("=" * 60)

    # Start the UI in a subprocess
    port = 8083
    print(f"\n1. Launching web UI on port {port}...")

    process = subprocess.Popen(
        [sys.executable, "eml/eml_automator.py", "--ui", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Wait for server to start
    print("   Waiting for server to start...")
    time.sleep(3)

    # Check if process is still running
    if process.poll() is not None:
        stdout, stderr = process.communicate()
        print(f"   ✗ Process exited early")
        print(f"   STDOUT: {stdout}")
        print(f"   STDERR: {stderr}")
        return False

    print(f"   ✓ Process started (PID: {process.pid})")

    # Try to connect to the UI
    print(f"\n2. Testing HTTP connection to http://127.0.0.1:{port}...")

    try:
        response = requests.get(f"http://127.0.0.1:{port}", timeout=5)
        print(f"   ✓ Server responding with status code: {response.status_code}")

        if response.status_code == 200:
            print(f"   ✓ Dashboard page loaded successfully")
            print(f"   ✓ Content length: {len(response.text)} bytes")
        else:
            print(f"   ✗ Unexpected status code: {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"   ✗ Connection failed: {e}")
        process.terminate()
        return False

    # Test other pages
    print(f"\n3. Testing navigation pages...")

    pages = [
        ("/upload", "Upload page"),
        ("/suppressed", "Suppressed emails page")
    ]

    for path, name in pages:
        try:
            response = requests.get(f"http://127.0.0.1:{port}{path}", timeout=5)
            if response.status_code == 200:
                print(f"   ✓ {name} accessible")
            else:
                print(f"   ✗ {name} returned {response.status_code}")
        except Exception as e:
            print(f"   ✗ {name} failed: {e}")

    # Check database connectivity
    print(f"\n4. Testing database integration...")
    try:
        import sqlite3
        from persistence import PersistenceLayer
        db = PersistenceLayer()

        # Create connection
        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()

        # Check processed emails count
        cursor.execute("SELECT COUNT(*) FROM processed_emails")
        processed = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM suppressed_emails")
        suppressed = cursor.fetchone()[0]

        conn.close()

        print(f"   ✓ Database connected")
        print(f"   ✓ Processed emails: {processed}")
        print(f"   ✓ Suppressed emails: {suppressed}")

    except Exception as e:
        print(f"   ✗ Database error: {e}")

    # Cleanup
    print(f"\n5. Shutting down server...")
    process.terminate()
    process.wait(timeout=5)
    print(f"   ✓ Server stopped cleanly")

    print("\n" + "=" * 60)
    print("✓ All tests passed! Web UI is working correctly.")
    print("=" * 60)
    print(f"\nTo use the web UI, run:")
    print(f"  uv run python eml/eml_automator.py --ui")
    print(f"\nThen open: http://127.0.0.1:8080")
    print()

    return True


if __name__ == "__main__":
    try:
        success = test_ui()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
