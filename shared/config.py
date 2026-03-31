"""
shared/config.py
Central configuration for the AI-Powered Ambient Stethoscope simulator.
All runtime paths are derived relative to this file so the project is
portable across environments.
"""

import os
from pathlib import Path

# ── Repository root (two levels up from this file) ────────────────────────────
REPO_ROOT: Path = Path(__file__).resolve().parent.parent

# ── MQTT ──────────────────────────────────────────────────────────────────────
MQTT_BROKER: str = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT: int = int(os.environ.get("MQTT_PORT", "1883"))

# Topic templates
TOPIC_SENSOR: str = "hospital/rooms/{room_id}/events"   # sensor_sim → backend
TOPIC_ALERTS: str = "hospital/alerts/{room_id}"         # backend   → dashboard / mobile / EHR

# ── Rooms ─────────────────────────────────────────────────────────────────────
ROOM_IDS: list[str] = ["312A", "312B", "313A", "313B", "314A", "314B"]

# ── Backend ───────────────────────────────────────────────────────────────────
BACKEND_HOST: str = os.environ.get("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT: int = int(os.environ.get("BACKEND_PORT", "8000"))
DB_PATH: str = os.environ.get(
    "DB_PATH",
    str(REPO_ROOT / "backend" / "hospital_data.db"),
)

# ── Dashboard ─────────────────────────────────────────────────────────────────
DASHBOARD_PORT: int = int(os.environ.get("DASHBOARD_PORT", "8501"))
BACKEND_API_URL: str = os.environ.get("BACKEND_API_URL", "http://localhost:8000")

# ── Sensor simulation ─────────────────────────────────────────────────────────
SENSOR_PUBLISH_INTERVAL_S: float = float(
    os.environ.get("SENSOR_PUBLISH_INTERVAL_S", "2.0")
)  # seconds between feature publishes per room

# Normal physiology ranges
NORMAL_BREATH_RATE_MEAN: float = 14.0   # bpm
NORMAL_BREATH_RATE_STD: float = 1.5
NORMAL_COUGH_PROB: float = 0.05         # probability per window
NORMAL_WHEEZE_PROB: float = 0.02
NORMAL_SPO2_MEAN: float = 97.5
NORMAL_SPO2_STD: float = 0.8
NORMAL_TEMP_MEAN: float = 37.0          # °C
NORMAL_TEMP_STD: float = 0.2

# Deterioration physiology ranges
DETN_BREATH_RATE_MEAN: float = 29.0
DETN_BREATH_RATE_STD: float = 3.0
DETN_COUGH_PROB: float = 0.65
DETN_WHEEZE_PROB: float = 0.50
DETN_SPO2_MEAN: float = 91.0
DETN_SPO2_STD: float = 1.5
DETN_TEMP_MEAN: float = 39.2
DETN_TEMP_STD: float = 0.4

# ── Alert engine thresholds ───────────────────────────────────────────────────
ALERT_COUGHS_PER_MIN_THRESHOLD: float = 4.0    # coughs/min over last window
ALERT_BREATH_RATE_LOW: float = 8.0             # bpm
ALERT_BREATH_RATE_HIGH: float = 24.0           # bpm
ALERT_SPO2_LOW: float = 94.0                   # %
ALERT_TEMP_HIGH: float = 38.0                  # °C
ALERT_RISK_SCORE_MEDIUM: float = 0.30
ALERT_RISK_SCORE_HIGH: float = 0.50
ALERT_RISK_SCORE_CRITICAL: float = 0.70

# Rolling window for risk score computation (seconds)
RISK_WINDOW_S: int = int(os.environ.get("RISK_WINDOW_S", "300"))  # 5 min

# ── EHR ───────────────────────────────────────────────────────────────────────
EHR_DB_PATH: str = os.environ.get(
    "EHR_DB_PATH",
    str(REPO_ROOT / "ehr" / "ehr_logs.db"),
)
