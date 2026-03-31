#!/usr/bin/env python3
"""
scripts/demo_clear_alert.py
Demo script: acknowledge all active alerts across all rooms.

Usage::

    python scripts/demo_clear_alert.py              # clear all rooms
    python scripts/demo_clear_alert.py 312A         # clear a specific room
"""

from __future__ import annotations

import os
import sys
import time

import requests

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from shared.config import BACKEND_API_URL

API = BACKEND_API_URL.rstrip("/")


def main() -> None:
    filter_room = sys.argv[1] if len(sys.argv) > 1 else None

    print("=" * 55)
    print("✓  Demo: Acknowledge all active alerts")
    if filter_room:
        print(f"   (filtered to room {filter_room})")
    print("=" * 55)

    try:
        alerts = requests.get(f"{API}/alerts", timeout=5).json()
    except Exception as exc:
        print(f"❌  Could not retrieve alerts: {exc}")
        sys.exit(1)

    if not alerts:
        print("  ℹ️  No active alerts to acknowledge.")
        return

    for alert in alerts:
        if filter_room and alert.get("room_id") != filter_room:
            continue
        alert_id = alert["id"]
        room_id = alert.get("room_id", "?")
        try:
            resp = requests.post(
                f"{API}/alerts/{alert_id}/acknowledge",
                json={"acknowledged_by": "demo_script"},
                timeout=5,
            )
            if resp.ok:
                print(f"  ✅  Alert #{alert_id} (Room {room_id}) acknowledged")
            else:
                print(f"  ⚠️  Alert #{alert_id} → {resp.status_code} {resp.text}")
        except requests.RequestException as exc:
            print(f"  ❌  Alert #{alert_id} → {exc}")
        time.sleep(0.05)

    print("\n✔  Done.  Dashboard should show cleared alerts.")


if __name__ == "__main__":
    main()
