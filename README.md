# AI-Powered Ambient Stethoscope for Hospital-Acquired Infections 🦠🔊

> **Privacy-preserving, full-stack software simulator** demonstrating passive
> respiratory monitoring for early Hospital-Acquired Pneumonia (HAP) detection.

This repository contains a full-stack software simulator for an AI-powered ambient stethoscope. The system is designed to passively monitor patients' respiratory sounds in a hospital setting, detect audible biomarkers of respiratory diseases like pneumonia, and alert healthcare providers to early signs of deterioration. It prioritizes privacy by processing audio on the edge and only transmitting high-level acoustic features, not raw audio.

## ✨ Key Features

| Feature | Description |
|---|---|
| **Passive monitoring** | No patient action required |
| **Privacy-by-design** | Acoustic *features* only — zero raw audio stored or transmitted |
| **Real-time alerts** | Escalating per-room HAP risk scores based on acoustic events |
| **Multi-room simulation** | Simulates 6 independent hospital rooms with unique patient states |
| **Multi-disease profiles** | Replicates acoustic patterns of different conditions (pneumonia, URI, sleep apnea) |
| **Patient-only sound isolation** | A model pipeline to extract coughs, sneezes, and crackles while suppressing conversations |
| **Live Demo** | A "Simulate Deterioration" feature to watch a patient's risk score escalate in real-time |

<br>

## 🚀 Getting Started

This project can be run locally using either Python directly or Docker.

### Prerequisites

- Python 3.10+
- [Pip](https://pip.pypa.io/en/stable/installation/)
- For the Docker-based setup: [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/install/)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/ai-powered-ambient-stethoscope.git
    cd ai-powered-ambient-stethoscope
    ```

2.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## 🏃‍♀️ Running the Simulation

You can run the entire simulation with a single command. The difference between `run_simulation.py` and `run_simulator.py` is purely for compatibility; they both launch the same full-stack application.

### Option A: Single Command (Recommended)

This command starts the backend, the embedded sensor simulator, and the dashboard.

```bash
python run_simulation.py
```

Once running, you can access:
- **Dashboard**: [http://localhost:8501](http://localhost:8501)
- **API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

### Option B: Docker Compose

This is an alternative way to run the project, with each service in its own container.

```bash
docker compose up --build
```

### Option C: Separate Terminals

For more granular control, you can run each component in a separate terminal.

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

**Via Dashboard:**
- Choose **Scenario** per room and click **Apply**
- Use different scenarios across rooms to compare disease probabilities live

**Via script:**
```bash
python scripts/demo_deterioration.py 312A
python scripts/demo_deterioration.py --scenario pneumonia_like 312B
python scripts/demo_multidisease.py
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

Note: the backend ACK endpoint now accepts both payload and payload-less POSTs,
so ACK buttons/scripts remain compatible across dashboard variants.

### 4. Restore normal
```bash
python scripts/demo_normal.py
```
or click **🟢 Restore** buttons in the dashboard.

---
## 🎧 Real Respiratory Sound Datasets + Model Pipeline

This repository includes an optional workflow to train a real-audio model for classifying respiratory events.

### 1. Download the Datasets

You will need to download the following datasets. Please review the license for each dataset before use.

- **COUGHVID**: A large dataset of coughs.
  - **Download**: [https://doi.org/10.5281/zenodo.7024894](https://doi.org/10.5281/zenodo.7024894)
- **ICBHI 2017 Challenge**: Contains respiratory cycles with crackles and wheezes.
  - **Download**: [https://bhichallenge.med.auth.gr/ICBHI_2017_Challenge](https://bhichallenge.med.auth.gr/ICBHI_2017_Challenge)
- **ESC-50**: Used for sourcing sneeze sounds.
  - **Download**: [https://github.com/karolpiczak/ESC-50](https://github.com/karolpiczak/ESC-50)

### 2. Structure the Datasets

After downloading and extracting the datasets, you should structure them within the `datasets/` directory as follows:

```
/ [repo_root]
└── datasets/
    ├── ESC-50-master/
    │   └── ESC-50-master/
    │       ├── audio/
    │       └── meta/
    │           └── esc50.csv
    ├── ICBHI_final_database/
    │   └── ICBHI_final_database/
    │       ├── 101_1b1_Al_sc_Meditron.txt
    │       ├── 101_1b1_Al_sc_Meditron.wav
    │       └── ...
    └── public_dataset_v3/
        └── coughvid_20211012/
            ├── metadata_compiled.csv
            ├── a00d99c2-c045-4240-9743-35f5243d9dd0.webm
            └── ...
```

### 3. Build the Manifest

Once the datasets are in place, run the following script to create a unified manifest file for training:

```bash
python scripts/build_real_audio_manifest.py 
  --icbhi-dir datasets/ICBHI_final_database/ICBHI_final_database 
  --coughvid-dir datasets/public_dataset_v3/coughvid_20211012 
  --esc50-dir datasets/ESC-50-master/ESC-50-master 
  --output datasets/real_audio_manifest.csv
```

### 4. Train the Classifier

With the manifest ready, you can train the classification model:

```bash
python scripts/train_real_audio_model.py 
  --manifest datasets/real_audio_manifest.csv 
  --output models/respiratory_event_model.joblib
```

### 5. Extract Patient Sounds

You can use the trained model to extract specific respiratory sounds from an audio file:

```bash
python scripts/extract_patient_sounds.py 
  --input <mixed_audio.wav> 
  --output outputs/patient_respiratory_events.wav 
  --model models/respiratory_event_model.joblib 
  --target-labels cough,sneeze,crackle,wheeze
```

---

## <details><summary>🏗️ Architecture</summary>

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
</details>

## <details><summary>🗂️ Directory Structure</summary>

```
/ [repo_root]
  sensor_sim/         Feature generator & MQTT publisher per room
    generator.py      Normal / deterioration scenario interpolation
    publisher.py      Per-room background thread publisher
    main.py           Entry point
  edge_ml/
    classifier.py     Rule-based event labeller (no audio used)
    real_audio.py     Optional real-dataset training/inference utilities
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
    demo_multidisease.py   Assign different diseases across rooms
    demo_clear_alert.py    Acknowledge all active alerts
    build_real_audio_manifest.py  Auto-build manifest from ICBHI + COUGHVID (+ ESC-50 sneeze)
    train_real_audio_model.py   Train classifier from real respiratory datasets
    extract_patient_sounds.py   Keep cough/sneeze/crackle/wheeze only
    real_audio_manifest_template.csv
  Dockerfile.backend
  Dockerfile.dashboard
  Dockerfile.sensor
  docker-compose.yml
  requirements.txt
  run_simulation.py   One-command launcher
  README.md
```
</details>

## <details><summary>⚙️ Configuration</summary>

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
</details>

## <details><summary>📡 API Reference</summary>

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

Supported scenario values:
- `normal`
- `deteriorating`
- `pneumonia_like`
- `uri_like`
- `sleep_apnea_like`
</details>

## <details><summary>🔒 Privacy-by-Design</summary>

- **No audio waveforms** are ever generated, stored, or transmitted
- All events carry only scalar acoustic features (breath rate, cough count, etc.)
- No patient names or real PII — patient IDs are placeholder strings
- The `RoomEvent` schema is the canonical privacy boundary
</details>

## <details><summary>✅ Publish-Ready Checklist</summary>
This repository now includes baseline release engineering assets:

- CI pipeline: `.github/workflows/ci.yml` (lint + type-check + tests on Python 3.10/3.11/3.12)
- Project metadata and tool configuration: `pyproject.toml`
- Contributor onboarding: `CONTRIBUTING.md`
- Security reporting policy: `SECURITY.md`
- Community conduct policy: `CODE_OF_CONDUCT.md`
- Example runtime environment file: `.env.example`
- Optional local hook automation: `.pre-commit-config.yaml`

Run the same quality gate locally before publishing:

```bash
pip install -r requirements.txt
pip install -e .[dev]
ruff check .
mypy backend edge_ml sensor_sim shared
pytest
```
</details>
