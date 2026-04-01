"""Orchestrator: Autonomous anomaly detection and notification pipeline.

Runs from 9:00 AM to 6:00 PM local time.
Every 5 seconds, Agent 01 (PyTorch) checks for anomalies.
If an anomaly is detected and the daily quota (10) is not exhausted,
Agent 03 (Gemini) is invoked for a control suggestion, which is then
sent to Discord via the MCP tool.
"""

import os
import sys
import time
import asyncio
import importlib.util
from datetime import datetime, date

# --- PATH SETUP ---
# Ensure we can import from the project root regardless of where we run
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGIC_DIR = os.path.join(SCRIPT_DIR, "..")
if LOGIC_DIR not in sys.path:
    sys.path.insert(0, LOGIC_DIR)

# Ensure Agent 01's directory is importable for its internal imports
AGENT01_DIR = os.path.join(LOGIC_DIR, "ai_pipelines", "01_traditional_ai")
if AGENT01_DIR not in sys.path:
    sys.path.insert(0, AGENT01_DIR)

from app.data_manager import extract_sensor_payload_at_index, get_electricity_len

# --- CONFIGURATION ---
TARGET_BUILDING = "Eagle_office_Marisela"
CHECK_INTERVAL_SECONDS = 5
MAX_DAILY_NOTIFICATIONS = 10
OPERATING_HOUR_START = 9   # 9:00 AM
OPERATING_HOUR_END = 18    # 6:00 PM
ANOMALY_THRESHOLD = 30.0   # % deviation to trigger Agent 03


# --- MODULE LOADERS ---
def _load_agent01():
    """Load Agent 01 (PyTorch) inference function."""
    path = os.path.join(AGENT01_DIR, "inference.py")
    spec = importlib.util.spec_from_file_location("agent01_inf", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.inference_step


def _load_agent03():
    """Load Agent 03 (Gemini Agentic) inference function."""
    agent03_dir = os.path.join(LOGIC_DIR, "ai_pipelines", "03_agentic_ai")
    path = os.path.join(agent03_dir, "inference.py")
    if agent03_dir not in sys.path:
        sys.path.insert(0, agent03_dir)
    spec = importlib.util.spec_from_file_location("agent03_inf", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.agentic_inference


# --- MCP CLIENT ---
async def _send_notification_via_mcp(tool_args: dict) -> str:
    """Connect to the MCP Server in-process and call the Discord tool."""
    from fastmcp import Client
    from notifications.mcp_server import mcp as mcp_server

    client = Client(mcp_server)
    async with client:
        result = await client.call_tool("send_discord_alert", tool_args)
        # result is a list of content blocks; extract text
        if result and hasattr(result[0], "text"):
            return result[0].text
        return str(result)


def _is_operating_hours() -> bool:
    """Check if current time is within the 9am-6pm operating window."""
    now = datetime.now()
    return OPERATING_HOUR_START <= now.hour < OPERATING_HOUR_END


def _detect_anomaly(predictions: dict) -> tuple[bool, str, float]:
    """Check if any metric exceeds the anomaly threshold.

    Returns:
        (is_anomaly, anomaly_type, deviation_percent)
    """
    for metric_name, label in [("electricity", "Electricity"), ("chilledwater", "Chilled Water")]:
        entry = predictions.get(metric_name, {})
        if "error" in entry:
            continue
        diff = entry.get("diff_percent", 0)
        if abs(diff) > ANOMALY_THRESHOLD:
            return True, label, diff
    return False, "", 0.0


def main():
    print("=" * 60)
    print("  SMART BUILDING 2.0 — NOTIFICATION ORCHESTRATOR")
    print(f"  Schedule: {OPERATING_HOUR_START}:00 — {OPERATING_HOUR_END}:00")
    print(f"  Interval: {CHECK_INTERVAL_SECONDS}s | Max alerts/day: {MAX_DAILY_NOTIFICATIONS}")
    print("=" * 60)

    # Load AI pipelines once at startup
    try:
        agent01_infer = _load_agent01()
        print("✅ Agent 01 (PyTorch) loaded.")
    except Exception as e:
        print(f"❌ Failed to load Agent 01: {e}")
        return

    try:
        agent03_infer = _load_agent03()
        print("✅ Agent 03 (Gemini Agentic) loaded.")
    except Exception as e:
        print(f"❌ Failed to load Agent 03: {e}")
        return

    # Dataset navigation (same 50% anti-leakage rule)
    total_len = get_electricity_len()
    start_idx = int(total_len * 0.5)
    current_idx = start_idx

    # Daily counter
    daily_count = 0
    last_reset_date = date.today()

    print(f"📊 Dataset range: {start_idx} → {total_len} ({total_len - start_idx} samples)")
    print("⏳ Waiting for operating hours..." if not _is_operating_hours() else "🟢 Within operating hours. Starting.")

    while True:
        # --- Daily counter reset ---
        today = date.today()
        if today != last_reset_date:
            daily_count = 0
            last_reset_date = today
            print(f"\n🔄 Daily counter reset. New day: {today}")

        # --- HARD STOP: quota exhausted ---
        if daily_count >= MAX_DAILY_NOTIFICATIONS:
            print(f"  ⏸️ Daily limit reached ({MAX_DAILY_NOTIFICATIONS}). Sleeping until next day or end of operating hours...")
            time.sleep(300)  # Sleep 5 minutes before re-checking
            continue

        # --- Operating hours check ---
        if not _is_operating_hours():
            time.sleep(30)  # Sleep longer outside hours
            continue

        # --- Extract sensor data ---
        payload = extract_sensor_payload_at_index(current_idx, [TARGET_BUILDING])
        b_data = payload.get("buildings", {}).get(TARGET_BUILDING, {})
        weather_keys = list(payload.get("weather", {}).keys())
        w_data = payload["weather"][weather_keys[0]] if weather_keys else {}

        air_temp = float(w_data.get("airTemperature", 15.0))
        wind_speed = float(w_data.get("windSpeed", 5.0))
        dew_temp = float(w_data.get("dewTemperature", 0.0) or 0.0)
        actual_elec = float(b_data.get("electricity_kwh", 0.0))
        actual_cw = float(b_data.get("chilledwater_kwh", 0.0))
        ts = payload.get("timestamp", "")

        try:
            hour = int(ts.split(" ")[1].split(":")[0]) if ts else 12
        except (IndexError, ValueError):
            hour = 12

        # --- Agent 01: Anomaly Detection ---
        try:
            predictions = agent01_infer(air_temp, wind_speed, hour, actual_elec, actual_cw, dew_temp=dew_temp)
        except Exception as e:
            print(f"[{ts}] Agent 01 error: {e}")
            current_idx += 1
            if current_idx >= total_len:
                current_idx = start_idx
            time.sleep(CHECK_INTERVAL_SECONDS)
            continue

        is_anomaly, anomaly_type, deviation = _detect_anomaly(predictions)

        if is_anomaly and daily_count < MAX_DAILY_NOTIFICATIONS:
            # INCREMENT COUNTER BEFORE any expensive call (Agent 03 / Gemini)
            # This guarantees the limit is enforced even if Agent 03 or
            # Discord throw exceptions, timeout, or fail silently.
            daily_count += 1
            print(f"\n🚨 [{ts}] ANOMALY: {anomaly_type} at {deviation:+.1f}% | Notification {daily_count}/{MAX_DAILY_NOTIFICATIONS} | Invoking Agent 03...")

            # --- Agent 03: Generate suggestion ---
            try:
                agent_result = agent03_infer(
                    air_temp, wind_speed, hour, actual_elec, actual_cw,
                    "LOW", "ON", dew_temp=dew_temp
                )
            except Exception as e:
                print(f"  Agent 03 error: {e}")
                agent_result = None

            if agent_result and agent_result.get("payload"):
                ap = agent_result["payload"]

                # --- MCP: Send Discord notification ---
                tool_args = {
                    "building_id": TARGET_BUILDING,
                    "anomaly_type": anomaly_type,
                    "deviation_percent": round(deviation, 1),
                    "agent_action": ap.get("action", "UNKNOWN"),
                    "agent_target": ap.get("target_equipment", "UNKNOWN"),
                    "agent_reasoning": ap.get("reasoning", ap.get("reason", "No reasoning")),
                    "estimated_savings": float(ap.get("estimated_savings_kwh", 0)),
                    "temperature": air_temp,
                    "dew_point": dew_temp,
                    "timestamp": ts,
                }

                try:
                    result = asyncio.run(_send_notification_via_mcp(tool_args))
                    print(f"  ✅ Discord sent ({daily_count}/{MAX_DAILY_NOTIFICATIONS}): {result}")
                except Exception as e:
                    print(f"  ❌ MCP/Discord error: {e}")
            else:
                print(f"  ⚠️ Agent 03 returned no actionable payload.")

            # If we've hit the limit, stop immediately
            if daily_count >= MAX_DAILY_NOTIFICATIONS:
                print(f"\n🛑 DAILY LIMIT REACHED ({MAX_DAILY_NOTIFICATIONS}). No more Gemini calls until tomorrow.")

        elif is_anomaly and daily_count >= MAX_DAILY_NOTIFICATIONS:
            pass  # Silently skip — hard stop at top of loop handles logging

        # --- Advance index ---
        current_idx += 1
        if current_idx >= total_len:
            current_idx = start_idx

        time.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
