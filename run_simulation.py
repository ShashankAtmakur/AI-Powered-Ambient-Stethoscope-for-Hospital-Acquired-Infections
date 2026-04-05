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
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable


def _spawn(name: str, cmd: list[str], extra_env: dict | None = None) -> subprocess.Popen:
    env = dict(os.environ)
    env["PYTHONPATH"] = REPO_ROOT
    if extra_env:
        env.update(extra_env)
    print(f"  ▶  Starting {name}…")
    return subprocess.Popen(cmd, env=env, cwd=REPO_ROOT)


def _is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _wait_for_port(host: str, port: int, timeout_s: float) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _is_port_open(host, port):
            return True
        time.sleep(0.2)
    return False


def _backend_healthy(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url.rstrip('/')}/health", timeout=2) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def main() -> None:
    procs: list[tuple[str, subprocess.Popen]] = []
    backend_host = "127.0.0.1"
    backend_port = int(os.getenv("BACKEND_PORT", "8000"))
    dashboard_port = int(os.getenv("DASHBOARD_PORT", "8501"))
    backend_url = os.getenv("BACKEND_API_URL", f"http://{backend_host}:{backend_port}")

    try:
        # 1. Backend (includes embedded sensor simulator)
        if _is_port_open(backend_host, backend_port):
            print(f"  ✓  Backend already running on {backend_host}:{backend_port}; reusing it.")
        else:
            backend = _spawn(
                "FastAPI Backend + Embedded Sensor Simulator",
                [
                    PYTHON,
                    "-m",
                    "uvicorn",
                    "backend.app:app",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    str(backend_port),
                ],
                extra_env={"EMBEDDED_SENSOR": "1"},
            )
            procs.append(("FastAPI Backend", backend))

            if not _wait_for_port(backend_host, backend_port, timeout_s=12):
                raise RuntimeError(
                    f"Backend failed to bind to {backend_host}:{backend_port}. "
                    "Check logs for startup errors."
                )

            if backend.poll() is not None:
                raise RuntimeError("Backend process exited during startup.")

            if not _backend_healthy(backend_url):
                raise RuntimeError(
                    "Backend did not pass health check after startup. "
                    f"Expected healthy endpoint at {backend_url}/health"
                )

        # 2. Streamlit dashboard
        if _is_port_open(backend_host, dashboard_port):
            print(f"  ✓  Dashboard already running on {backend_host}:{dashboard_port}; reusing it.")
        else:
            dashboard = _spawn(
                "Streamlit Dashboard",
                [
                    PYTHON,
                    "-m",
                    "streamlit",
                    "run",
                    "dashboard/streamlit_app.py",
                    f"--server.port={dashboard_port}",
                    "--server.headless=true",
                    "--server.address=0.0.0.0",
                ],
                extra_env={"BACKEND_API_URL": backend_url},
            )
            procs.append(("Streamlit Dashboard", dashboard))

            if not _wait_for_port(backend_host, dashboard_port, timeout_s=12):
                raise RuntimeError(
                    f"Dashboard failed to bind to {backend_host}:{dashboard_port}. "
                    "Check logs for startup errors."
                )

            if dashboard.poll() is not None:
                raise RuntimeError("Dashboard process exited during startup.")

        print()
        print("=" * 62)
        print("🎉  AI-Powered Ambient Stethoscope Simulator Running!")
        print("=" * 62)
        print(f"  📊  Dashboard     → http://localhost:{dashboard_port}")
        print(f"  🔌  Backend API   → {backend_url}")
        print(f"  📖  API Docs      → {backend_url}/docs")
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
            for name, proc in procs:
                if proc.poll() is not None:
                    raise RuntimeError(f"{name} exited unexpectedly with code {proc.returncode}.")
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
