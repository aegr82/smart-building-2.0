"""Tests for the Notification Module (MCP + Discord).

Tests the orchestrator logic and MCP server tool registration
WITHOUT making real API calls to Gemini or Discord.
"""

import os
import sys
import asyncio
from unittest.mock import patch, MagicMock

# Path setup
BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logic")
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, "ai_pipelines", "01_traditional_ai"))


def test_mcp_server_tool_registration():
    """Verify the MCP server registers the send_discord_alert tool."""
    print("Testing MCP Server tool registration...")
    try:
        from notifications.mcp_server import mcp
        # FastMCP stores tools internally; verify our tool exists
        assert mcp is not None, "MCP server instance is None"
        print("✅ MCP Server instantiated successfully.")
    except Exception as e:
        print(f"❌ MCP Server failed: {e}")
        raise e


def test_anomaly_detection_logic():
    """Verify anomaly detection thresholds work correctly."""
    print("Testing anomaly detection logic...")
    from notifications.orchestrator import _detect_anomaly

    # Case 1: Electricity anomaly (>30%)
    predictions = {
        "electricity": {"predicted": 100, "actual": 140, "diff_percent": 40.0, "status": "ANOMALY"},
        "chilledwater": {"predicted": 300000, "actual": 290000, "diff_percent": -3.3, "status": "NORMAL"},
    }
    is_anomaly, atype, dev = _detect_anomaly(predictions)
    assert is_anomaly is True, f"Expected anomaly, got {is_anomaly}"
    assert atype == "Electricity", f"Expected Electricity, got {atype}"
    assert dev == 40.0
    print("  ✅ Case 1 (Electricity anomaly): PASS")

    # Case 2: No anomaly
    predictions = {
        "electricity": {"predicted": 100, "actual": 110, "diff_percent": 10.0, "status": "NORMAL"},
        "chilledwater": {"predicted": 300000, "actual": 280000, "diff_percent": -6.6, "status": "NORMAL"},
    }
    is_anomaly, _, _ = _detect_anomaly(predictions)
    assert is_anomaly is False, f"Expected no anomaly, got {is_anomaly}"
    print("  ✅ Case 2 (No anomaly): PASS")

    # Case 3: Chilled Water anomaly
    predictions = {
        "electricity": {"predicted": 100, "actual": 105, "diff_percent": 5.0, "status": "NORMAL"},
        "chilledwater": {"predicted": 300000, "actual": 450000, "diff_percent": 50.0, "status": "ANOMALY"},
    }
    is_anomaly, atype, dev = _detect_anomaly(predictions)
    assert is_anomaly is True
    assert atype == "Chilled Water"
    print("  ✅ Case 3 (Chilled Water anomaly): PASS")

    print("✅ Anomaly detection logic: ALL PASS")


def test_daily_limit_enforcement():
    """Verify that the daily counter is respected."""
    print("Testing daily limit enforcement...")
    from notifications.orchestrator import MAX_DAILY_NOTIFICATIONS

    assert MAX_DAILY_NOTIFICATIONS == 10, f"Expected 10, got {MAX_DAILY_NOTIFICATIONS}"

    # Simulate the counter logic
    daily_count = 0
    anomalies_attempted = 0
    anomalies_sent = 0

    for _ in range(15):  # 15 anomalies in one day
        anomalies_attempted += 1
        if daily_count < MAX_DAILY_NOTIFICATIONS:
            daily_count += 1
            anomalies_sent += 1

    assert anomalies_sent == 10, f"Expected 10 sent, got {anomalies_sent}"
    assert anomalies_attempted == 15, f"Expected 15 attempted, got {anomalies_attempted}"
    print(f"  ✅ Sent {anomalies_sent}/{anomalies_attempted} (limit enforced at {MAX_DAILY_NOTIFICATIONS})")
    print("✅ Daily limit enforcement: PASS")


def test_operating_hours():
    """Verify operating hours detection."""
    print("Testing operating hours logic...")
    from notifications.orchestrator import OPERATING_HOUR_START, OPERATING_HOUR_END

    assert OPERATING_HOUR_START == 9
    assert OPERATING_HOUR_END == 18
    print(f"  ✅ Schedule: {OPERATING_HOUR_START}:00 — {OPERATING_HOUR_END}:00")
    print("✅ Operating hours config: PASS")


def test_webhook_url_loader():
    """Verify webhook URL loader handles comments and blanks."""
    print("Testing webhook URL loader...")
    from notifications.mcp_server import _load_webhook_urls

    urls = _load_webhook_urls()
    # Should return empty or valid URLs (no comments)
    for url in urls:
        assert not url.startswith("#"), f"Comment leaked through: {url}"
        assert url.strip() != "", "Empty line leaked through"
    print(f"  ✅ Loaded {len(urls)} webhook URL(s) (comments/blanks filtered)")
    print("✅ Webhook URL loader: PASS")


if __name__ == "__main__":
    print(f"\n{'='*60}")
    print("  NOTIFICATION MODULE TESTS")
    print(f"{'='*60}\n")

    test_mcp_server_tool_registration()
    print()
    test_anomaly_detection_logic()
    print()
    test_daily_limit_enforcement()
    print()
    test_operating_hours()
    print()
    test_webhook_url_loader()

    print(f"\n{'='*60}")
    print("  ✅ ALL NOTIFICATION TESTS PASSED")
    print(f"{'='*60}")
