"""MCP Server: Exposes Discord notification as a tool via Model Context Protocol.

The orchestrator calls this tool through the MCP client interface whenever
Agent 03 generates a control suggestion that needs to be broadcast.
"""

import os
import httpx
from fastmcp import FastMCP

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS_FILE = os.path.join(MODULE_DIR, "accounts.txt")

mcp = FastMCP("SmartBuildingNotifications")


def _load_webhook_urls() -> list[str]:
    """Reads webhook URLs from accounts.txt, ignoring comments and blanks."""
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    urls = []
    with open(ACCOUNTS_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls


@mcp.tool()
def send_discord_alert(
    building_id: str,
    anomaly_type: str,
    deviation_percent: float,
    agent_action: str,
    agent_target: str,
    agent_reasoning: str,
    estimated_savings: float,
    temperature: float,
    dew_point: float,
    timestamp: str,
) -> str:
    """Send a formatted anomaly alert to all configured Discord channels.

    Args:
        building_id: The building where the anomaly was detected.
        anomaly_type: Which metric is anomalous (e.g. "Electricity", "Chilled Water").
        deviation_percent: How far actual deviates from predicted (%).
        agent_action: The action decided by Agent 03 (e.g. TURN_OFF).
        agent_target: The equipment targeted (e.g. Chiller, Lighting).
        agent_reasoning: The full reasoning from Agent 03.
        estimated_savings: Estimated kWh savings.
        temperature: Current air temperature in Celsius.
        dew_point: Current dew temperature in Celsius.
        timestamp: The sensor timestamp.

    Returns:
        A summary of delivery results.
    """
    webhook_urls = _load_webhook_urls()
    if not webhook_urls:
        return "ERROR: No webhook URLs configured in accounts.txt"

    # Build Discord Embed
    color = 0xFF4444 if "TURN_OFF" in agent_action else 0x44BB44
    embed = {
        "title": f"🚨 Anomalía Detectada — {building_id}",
        "color": color,
        "fields": [
            {"name": "📊 Tipo de Anomalía", "value": anomaly_type, "inline": True},
            {"name": "📈 Desviación", "value": f"{deviation_percent:+.1f}%", "inline": True},
            {"name": "🌡️ Clima", "value": f"{temperature}°C (Rocío: {dew_point}°C)", "inline": True},
            {"name": "⚙️ Acción", "value": f"**{agent_action}** → {agent_target}", "inline": False},
            {"name": "🧠 Razonamiento", "value": agent_reasoning[:1024], "inline": False},
            {"name": "💡 Ahorro Estimado", "value": f"{estimated_savings:.1f} kWh", "inline": True},
            {"name": "🕐 Timestamp", "value": timestamp, "inline": True},
        ],
        "footer": {"text": "Smart Building 2.0 — Autonomous Control Agent"},
    }

    payload = {
        "username": "BMS Agent",
        "embeds": [embed],
    }

    results = []
    with httpx.Client(timeout=10.0) as client:
        for url in webhook_urls:
            try:
                resp = client.post(url, json=payload)
                if resp.status_code in (200, 204):
                    results.append(f"OK ({url[-12:]})")
                else:
                    results.append(f"HTTP {resp.status_code} ({url[-12:]})")
            except Exception as e:
                results.append(f"FAIL: {e}")

    summary = f"Delivered to {len(webhook_urls)} channel(s): {', '.join(results)}"
    print(f"[MCP Discord] {summary}")
    return summary


if __name__ == "__main__":
    mcp.run()
