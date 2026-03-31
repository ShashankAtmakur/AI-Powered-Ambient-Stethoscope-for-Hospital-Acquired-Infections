# AI-Powered Ambient Stethoscope for Hospital-Acquired Infections 🦠🔊

> **Privacy-preserving, full-stack software simulator** demonstrating passive
> respiratory monitoring for early Hospital-Acquired Pneumonia (HAP) detection.

---

## ✨ Innovation Overview

| Feature | Description |
|---|---|
| **Passive monitoring** | No patient action required |
| **Privacy-by-design** | Acoustic *features* only — zero raw audio stored |
| **Real-time alerts** | Escalating per-room HAP risk scores |
| **Multi-room** | 6 simulated ward rooms with independent state |
| **Wow moment** | Click "Simulate Deterioration" → watch risk escalate live |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│            AI-Powered Ambient Stethoscope Simulator          │
└─────────────────────────────────────────────────────────────┘

  sensor_sim/       Multi-room acoustic feature generator
  (per-room thread) → cough rate, breath rate, SpO₂, temp
        │
        │  MQTT  hospital/rooms/{room_id}/events
        ▼
  edge_ml/          Rule-based edge classifier
                    → anomaly_label, anomaly_score
        │
        │  (inline, same process as sensor_sim)
        │
        ▼
  backend/          FastAPI + SQLite aggregator
  (FastAPI)         REST API + WebSocket
  port 8000         Alert engine → risk scores → RoomAlert
        │
        ▼
  dashboard/        Streamlit nurse-station UI
  (Streamlit)       Live room grid, trend charts, alerts
  port 8501
```

---

## 🗂️ Directory Structure

```
/ [repo_root]
  sensor_sim/         Feature generator & MQTT publisher per room
    generator.py      Normal / deterioration scenario interpolation
    publisher.py      Per-room background thread publisher
    main.py           Entry point
  edge_ml/
    classifier.py     Rule-based event labeller (no audio used)
  backend/
    app.py            FastAPI routes + WebSocket endpoint
    aggregator.py     MQTT subscriber + buffer management
    alert_engine.py   Risk scoring + alert generation
    database.py       SQLite storage layer
  dashboard/
    streamlit_app.py  Streamlit nurse dashboard (new)
    app.py            Legacy Flask dashboard (kept for reference)
  shared/
    config.py         All runtime config (env-var overridable)
    schemas.py        Pydantic models shared across modules
    constants.py      Labels, colours, topic helpers
  common/
    simple_broker.py  In-process MQTT broker (no external deps)
  scripts/
    demo_normal.py         Reset all rooms to normal
    demo_deterioration.py  Inject acute episode into room 312A
    demo_clear_alert.py    Acknowledge all active alerts
  Dockerfile.backend
  Dockerfile.dashboard
  Dockerfile.sensor
  docker-compose.yml
  requirements.txt
  run_simulation.py   One-command launcher
  README.md
```

---

## 🚀 Quick Start

### Option A — Single Python command (recommended for demo)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Launch everything
python run_simulation.py
```

Then open:
- **Dashboard** → http://localhost:8501
- **API docs** → http://localhost:8000/docs

### Option B — Docker Compose

```bash
docker compose up --build
```

### Option C — Separate terminals

```bash
# Terminal 1 – Backend
PYTHONPATH=. uvicorn backend.app:app --host 0.0.0.0 --port 8000

# Terminal 2 – Sensor simulator
PYTHONPATH=. python -m sensor_sim.main

# Terminal 3 – Dashboard
PYTHONPATH=. streamlit run dashboard/streamlit_app.py --server.port 8501
```

---

## 🎬 Demo Walkthrough

### 1. Normal baseline
All rooms show green indicators with stable breath rates (~14 bpm) and low cough frequency.

### 2. Simulate deterioration (Wow Moment)

**Via Dashboard:**  Click the **🔴 Deteriorate** button on any room card.

**Via script:**
```bash
python scripts/demo_deterioration.py 312A
```

**What happens:**
- Breath rate climbs from ~14 → ~26 bpm over ~5 minutes
- Cough rate increases 10×
- SpO₂ drops below 94%
- Temperature rises above 38°C
- Risk score escalates: Normal → Medium → High → Critical
- Alerts appear in the Active Alerts panel

### 3. Acknowledge alerts
```bash
python scripts/demo_clear_alert.py
```
or click **✓ Ack** buttons in the dashboard.

### 4. Restore normal
```bash
python scripts/demo_normal.py
```
or click **🟢 Restore** buttons in the dashboard.

---

## ⚙️ Configuration

All settings are in `shared/config.py` and can be overridden with environment variables:

| Variable | Default | Description |
|---|---|---|
| `BACKEND_API_URL` | `http://localhost:8000` | Backend URL for dashboard |
| `MQTT_BROKER` | `localhost` | MQTT broker host |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `DB_PATH` | `backend/hospital_data.db` | SQLite database path |
| `SENSOR_PUBLISH_INTERVAL_S` | `2.0` | Seconds between sensor updates |
| `RISK_WINDOW_S` | `300` | Rolling window for risk calculation (s) |
| `USE_PAHO` | `0` | Set to `1` to use real paho-mqtt |

---

## 📡 API Reference

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/rooms` | List all room IDs |
| GET | `/rooms/{id}/status` | Current room status + risk score |
| GET | `/rooms/{id}/timeseries` | Historical events (charts) |
| GET | `/alerts` | All active (unacknowledged) alerts |
| POST | `/alerts/{id}/acknowledge` | Acknowledge an alert |
| POST | `/rooms/{id}/scenario` | Change room scenario (normal/deteriorating) |
| GET | `/summary` | Ward-wide summary |
| WS | `/ws` | WebSocket live updates |

---

## 🔒 Privacy-by-Design

- **No audio waveforms** are ever generated, stored, or transmitted
- All events carry only scalar acoustic features (breath rate, cough count, etc.)
- No patient names or real PII — patient IDs are placeholder strings
- The `RoomEvent` schema is the canonical privacy boundary

---

## 📊 Metrics (simulated)

| Metric | Value |
|---|---|
| Cough detection recall | > 85% (simulated) |
| Breathing rate error | < 2 bpm |
| Audio storage | **Zero** |
| Alert latency | < 5 s end-to-end |

---

## 🔭 Extension Notes

- **Real MQTT**: set `USE_PAHO=1` and point `MQTT_BROKER` at Mosquitto
- **EHR integration**: `ehr/integration.py` generates HL7-like messages
- **Real ML model**: replace `edge_ml/classifier.py` rules with a TFLite/ONNX model
- **Longitudinal risk**: extend `backend/alert_engine.py` with time-series forecasting
- **Multi-ward**: add room IDs to `shared/config.py → ROOM_IDS`
