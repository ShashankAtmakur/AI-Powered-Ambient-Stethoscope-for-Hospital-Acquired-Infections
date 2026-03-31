#!/usr/bin/env python3
"""
scripts/demo_normal.py
Demo script: run all rooms in the normal (healthy) scenario.
Sends a scenario-reset request to the backend REST API for every room.

Usage::

    python scripts/demo_normal.py
"""

from __future__ import annotations

import os
import sys
import time

import requests

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from shared.config import BACKEND_API_URL, ROOM_IDS

API = BACKEND_API_URL.rstrip("/")


def main() -> None:
    print("=" * 55)
    print("🟢  Demo: Normal (Healthy) Scenario for all rooms")
    print("=" * 55)
    for room_id in ROOM_IDS:
        try:
            resp = requests.post(
                f"{API}/rooms/{room_id}/scenario",
                json={"room_id": room_id, "scenario": "normal"},
                timeout=5,
            )
            if resp.ok:
                print(f"  ✅  Room {room_id} → normal")
            else:
                print(f"  ⚠️  Room {room_id} → {resp.status_code} {resp.text}")
        except requests.RequestException as exc:
            print(f"  ❌  Room {room_id} → connection error: {exc}")
        time.sleep(0.1)

    print("\n✔  All rooms set to NORMAL.  Watch the dashboard for green indicators.")


if __name__ == "__main__":
    main()
