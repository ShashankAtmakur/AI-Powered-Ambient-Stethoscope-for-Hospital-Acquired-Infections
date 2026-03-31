#!/usr/bin/env python3
"""
run_simulation.py
Single-command launcher for the complete AI Ambient Stethoscope simulator.

Architecture
------------
The backend runs in embedded mode (EMBEDDED_SENSOR=1), starting the multi-room
sensor simulator in-process so that both share the same in-memory MQTT broker.
The Streamlit dashboard is launched as a separate process and communicates with
the backend via REST/WebSocket.

Usage::

    python run_simulation.py

Stop with Ctrl+C.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable


def _spawn(name: str, cmd: list[str], extra_env: dict | None = None) -> subprocess.Popen:
    env = dict(os.environ)
    env["PYTHONPATH"] = REPO_ROOT
    if extra_env:
        env.update(extra_env)
    print(f"  ▶  Starting {name}…")
    return subprocess.Popen(cmd, env=env, cwd=REPO_ROOT)


def main() -> None:
    procs: list[tuple[str, subprocess.Popen]] = []

    try:
        # 1. Backend (includes embedded sensor simulator)
        backend = _spawn(
            "FastAPI Backend + Embedded Sensor Simulator",
            [PYTHON, "-m", "uvicorn", "backend.app:app",
             "--host", "0.0.0.0", "--port", "8000"],
            extra_env={"EMBEDDED_SENSOR": "1"},
        )
        procs.append(("FastAPI Backend", backend))
        time.sleep(3)   # wait for backend + simulator to start

        # 2. Streamlit dashboard
        dashboard = _spawn(
            "Streamlit Dashboard",
            [PYTHON, "-m", "streamlit", "run",
             "dashboard/streamlit_app.py",
             "--server.port=8501",
             "--server.headless=true",
             "--server.address=0.0.0.0"],
            extra_env={"BACKEND_API_URL": "http://localhost:8000"},
        )
        procs.append(("Streamlit Dashboard", dashboard))

        print()
        print("=" * 62)
        print("🎉  AI-Powered Ambient Stethoscope Simulator Running!")
        print("=" * 62)
        print("  📊  Dashboard     → http://localhost:8501")
        print("  🔌  Backend API   → http://localhost:8000")
        print("  📖  API Docs      → http://localhost:8000/docs")
        print()
        print("  Demo scripts (run in another terminal):")
        print("    python scripts/demo_deterioration.py       # inject episode")
        print("    python scripts/demo_clear_alert.py         # acknowledge all")
        print("    python scripts/demo_normal.py              # restore baseline")
        print()
        print("  Press Ctrl+C to stop all components.")
        print("=" * 62)

        def _shutdown(sig, frame):  # noqa: ANN001
            print("\nShutting down…")
            for name, proc in procs:
                print(f"  ■  Stopping {name}…")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
            sys.exit(0)

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        for _, proc in procs:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
