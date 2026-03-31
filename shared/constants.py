"""
shared/constants.py
Named constants used across the simulator for labels, colours, and formatting.
"""

# Anomaly / risk label strings
LABEL_NORMAL = "normal"
LABEL_MILD = "mild"
LABEL_MODERATE = "moderate"
LABEL_SEVERE = "severe"

ANOMALY_LABELS = [LABEL_NORMAL, LABEL_MILD, LABEL_MODERATE, LABEL_SEVERE]

# Dashboard colour map for Streamlit
RISK_COLORS: dict[str, str] = {
    "normal": "#27ae60",    # green
    "medium": "#f39c12",    # amber
    "high": "#e67e22",      # orange
    "critical": "#e74c3c",  # red
}

SEVERITY_EMOJI: dict[str, str] = {
    "medium": "🔔",
    "high": "⚠️",
    "critical": "🚨",
}

# MQTT topic helpers
def topic_sensor(room_id: str) -> str:
    """Return the MQTT topic for sensor events of a room."""
    from shared.config import TOPIC_SENSOR
    return TOPIC_SENSOR.format(room_id=room_id)


def topic_alerts(room_id: str) -> str:
    """Return the MQTT topic for alerts of a room."""
    from shared.config import TOPIC_ALERTS
    return TOPIC_ALERTS.format(room_id=room_id)
