#!/usr/bin/env python3
"""
Test script to verify Analytics page functionality
"""

import sys
import os
import time
import subprocess
import requests
from pathlib import Path

def test_analytics():
    """Test the Analytics page by launching UI and checking charts"""

    print("=" * 60)
    print("Testing CRM Automator Analytics Page")
    print("=" * 60)

    # Start the UI in a subprocess
    port = 8084
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

    # Test main pages
    print(f"\n2. Testing page accessibility...")

    pages_to_test = [
        ("/", "Dashboard"),
        ("/upload", "Upload page"),
        ("/analytics", "Analytics page"),
        ("/suppressed", "Suppressed emails page")
    ]

    for path, name in pages_to_test:
        try:
            response = requests.get(f"http://127.0.0.1:{port}{path}", timeout=5)
            if response.status_code == 200:
                print(f"   ✓ {name} accessible (HTTP {response.status_code})")
                # Check if analytics has plotly content
                if path == "/analytics" and "plotly" in response.text.lower():
                    print(f"     ✓ Analytics page contains Plotly charts")
            else:
                print(f"   ✗ {name} returned {response.status_code}")
                return False
        except Exception as e:
            print(f"   ✗ {name} failed: {e}")
            return False

    # Test AnalyticsEngine directly
    print(f"\n3. Testing AnalyticsEngine functionality...")
    try:
        from web_ui import AnalyticsEngine
        analytics = AnalyticsEngine()

        # Test stats retrieval
        stats = analytics.get_processing_stats()
        print(f"   ✓ Processing stats retrieved: {stats}")

        # Test chart creation (with empty data)
        pie_chart = analytics.create_processing_pie_chart(stats)
        print(f"   ✓ Pie chart created: {type(pie_chart).__name__}")

        gauge_chart = analytics.create_success_gauge_chart(stats)
        print(f"   ✓ Gauge chart created: {type(gauge_chart).__name__}")

        # Test category breakdown
        category_data = analytics.get_suppression_breakdown()
        print(f"   ✓ Category breakdown: {len(category_data)} categories")

        # Test timeline data
        timeline_data = analytics.get_timeline_data(days=7)
        print(f"   ✓ Timeline data: {len(timeline_data.get('dates', []))} days")

        # Test top domains
        top_domains = analytics.get_top_suppressed_domains(limit=5)
        print(f"   ✓ Top domains: {len(top_domains)} domains")

    except Exception as e:
        print(f"   ✗ AnalyticsEngine error: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Cleanup
    print(f"\n4. Shutting down server...")
    process.terminate()
    process.wait(timeout=5)
    print(f"   ✓ Server stopped cleanly")

    print("\n" + "=" * 60)
    print("✓ All Analytics tests passed!")
    print("=" * 60)
    print(f"\nTo use the Analytics page:")
    print(f"  1. Run: uv run python eml/eml_automator.py --ui")
    print(f"  2. Open: http://127.0.0.1:8080")
    print(f"  3. Click: 'View Analytics' or navigate to /analytics")
    print()
    print("Features:")
    print("  • Processing Overview (Pie Chart)")
    print("  • Success Rate Gauge")
    print("  • Suppression by Category (Bar Chart)")
    print("  • Processing Timeline (Line Chart)")
    print("  • Top Suppressed Domains")
    print("  • Suppression by Reason")
    print()

    return True


if __name__ == "__main__":
    try:
        success = test_analytics()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
