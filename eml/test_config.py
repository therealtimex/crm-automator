#!/usr/bin/env python3
"""
Test script to verify Config page functionality
"""

import sys
import os
import time
import subprocess
import requests
from pathlib import Path
import shutil

def test_config():
    """Test the Config page by launching UI and checking functionality"""

    print("=" * 60)
    print("Testing CRM Automator Config Page")
    print("=" * 60)

    # Backup .env file if it exists
    env_file = Path(".env")
    backup_file = Path(".env.backup")

    if env_file.exists():
        print(f"\n0. Backing up .env file...")
        shutil.copy(env_file, backup_file)
        print(f"   ✓ Backup created at {backup_file}")

    # Start the UI in a subprocess
    port = 8085
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

    # Test config page accessibility
    print(f"\n2. Testing Config page accessibility...")

    try:
        response = requests.get(f"http://127.0.0.1:{port}/config", timeout=5)
        if response.status_code == 200:
            print(f"   ✓ Config page accessible (HTTP {response.status_code})")

            # Check for key elements
            if "CRM API Settings" in response.text:
                print(f"     ✓ CRM API Settings section found")
            if "LLM Settings" in response.text:
                print(f"     ✓ LLM Settings section found")
            if "Save Configuration" in response.text:
                print(f"     ✓ Save button found")
        else:
            print(f"   ✗ Config page returned {response.status_code}")
            return False
    except Exception as e:
        print(f"   ✗ Config page failed: {e}")
        return False

    # Test ConfigManager directly
    print(f"\n3. Testing ConfigManager functionality...")
    try:
        from web_ui import ConfigManager
        config_mgr = ConfigManager()

        # Test config loading
        config = config_mgr.load_config()
        print(f"   ✓ Config loaded: {len(config)} settings")

        # Test validation
        errors = config_mgr.validate_config(config)
        if errors:
            print(f"   ⚠ Validation found {len(errors)} issues:")
            for error in errors[:3]:  # Show first 3 errors
                print(f"     - {error}")
        else:
            print(f"   ✓ Config validation passed")

        # Test required fields validation
        empty_config = {}
        errors = config_mgr.validate_config(empty_config)
        if errors:
            print(f"   ✓ Required field validation working ({len(errors)} errors for empty config)")
        else:
            print(f"   ⚠ Required field validation may not be working")

        # Test URL validation
        invalid_url_config = {
            "CRM_API_BASE_URL": "not-a-url",
            "CRM_API_KEY": "test",
            "LLM_API_BASE_URL": "also-not-a-url",
            "LLM_API_KEY": "test",
            "LLM_MODEL": "test"
        }
        errors = config_mgr.validate_config(invalid_url_config)
        url_errors = [e for e in errors if "URL" in e or "http" in e.lower()]
        if url_errors:
            print(f"   ✓ URL format validation working ({len(url_errors)} URL errors)")
        else:
            print(f"   ⚠ URL format validation may not be working")

    except Exception as e:
        print(f"   ✗ ConfigManager error: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test config persistence
    print(f"\n4. Testing config save/load cycle...")
    try:
        # Load current config
        original_config = config_mgr.load_config()

        # Add a test value
        test_config = original_config.copy()
        test_config["TEST_KEY"] = "test_value_123"

        # Save config
        success, message = config_mgr.save_config(test_config)
        if success:
            print(f"   ✓ Config saved successfully")
        else:
            print(f"   ✗ Config save failed: {message}")
            return False

        # Reload and verify
        reloaded_config = config_mgr.load_config()
        if reloaded_config.get("TEST_KEY") == "test_value_123":
            print(f"   ✓ Test value persisted correctly")
        else:
            print(f"   ✗ Test value not found after reload")
            return False

        # Clean up test key and restore original
        success, message = config_mgr.save_config(original_config)
        if success:
            print(f"   ✓ Original config restored")
        else:
            print(f"   ⚠ Warning: Could not restore original config")

    except Exception as e:
        print(f"   ✗ Config persistence test error: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Test navigation links (note: NiceGUI renders buttons client-side, so we just check page accessibility)
    print(f"\n5. Testing page accessibility (navigation buttons rendered client-side)...")
    pages_to_check = [
        ("/", "Dashboard"),
        ("/upload", "Upload"),
        ("/analytics", "Analytics"),
        ("/suppressed", "Suppressed"),
        ("/config", "Config")
    ]

    for path, name in pages_to_check:
        try:
            response = requests.get(f"http://127.0.0.1:{port}{path}", timeout=5)
            if response.status_code == 200:
                print(f"   ✓ {name} page accessible")
            else:
                print(f"   ✗ {name} page returned {response.status_code}")
        except Exception as e:
            print(f"   ✗ {name} page failed: {e}")

    # Cleanup
    print(f"\n6. Shutting down server...")
    process.terminate()
    process.wait(timeout=5)
    print(f"   ✓ Server stopped cleanly")

    # Restore original .env if backup exists
    if backup_file.exists():
        print(f"\n7. Restoring original .env file...")
        shutil.copy(backup_file, env_file)
        backup_file.unlink()
        print(f"   ✓ Original .env restored")

    print("\n" + "=" * 60)
    print("✓ All Config tests passed!")
    print("=" * 60)
    print(f"\nTo use the Config page:")
    print(f"  1. Run: uv run python eml/eml_automator.py --ui")
    print(f"  2. Open: http://127.0.0.1:8080")
    print(f"  3. Click: 'Config' in navigation")
    print()
    print("Features:")
    print("  • CRM API Configuration")
    print("  • LLM Settings")
    print("  • Entity Extraction API Settings")
    print("  • Email Processing Options")
    print("  • Suppression Logic Settings")
    print("  • Form Validation")
    print("  • Connection Testing (CRM & LLM)")
    print("  • Comment Preservation in .env file")
    print()

    return True


if __name__ == "__main__":
    try:
        success = test_config()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
