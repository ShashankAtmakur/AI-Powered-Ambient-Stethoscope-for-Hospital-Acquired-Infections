#!/usr/bin/env python3
"""
scripts/demo_deterioration.py
Demo script: inject an acute deterioration episode into one or more rooms.

This is the "Wow Moment" trigger:
  - Sets the target room(s) to the DETERIORATING scenario via the REST API
  - The sensor simulator gradually ramps up cough rate, breath rate, temperature,
    and drops SpO₂ over ~5 minutes
  - The alert engine will raise escalating alerts visible on the dashboard

Usage::

    python scripts/demo_deterioration.py                  # room 312A
    python scripts/demo_deterioration.py 312B 313A        # custom rooms
    python scripts/demo_deterioration.py --scenario pneumonia_like 312A
"""

from __future__ import annotations

import os
import sys
import time
import argparse

import requests

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from shared.config import BACKEND_API_URL, ROOM_IDS

API = BACKEND_API_URL.rstrip("/")
DEFAULT_ROOMS = ["312A"]


def deteriorate(room_id: str, scenario: str) -> None:
    try:
        resp = requests.post(
            f"{API}/rooms/{room_id}/scenario",
            json={"room_id": room_id, "scenario": scenario},
            timeout=5,
        )
        if resp.ok:
            print(f"  🔴  Room {room_id} → {scenario.upper()} scenario injected")
        else:
            print(f"  ⚠️  Room {room_id} → {resp.status_code} {resp.text}")
    except requests.RequestException as exc:
        print(f"  ❌  Room {room_id} → connection error: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        default="deteriorating",
        choices=["deteriorating", "pneumonia_like", "uri_like", "sleep_apnea_like"],
        help="Scenario to inject",
    )
    parser.add_argument("rooms", nargs="*", help="Room IDs")
    args = parser.parse_args()

    target_rooms = args.rooms if args.rooms else DEFAULT_ROOMS
    invalid = [r for r in target_rooms if r not in ROOM_IDS]
    if invalid:
        print(f"⚠️  Unknown rooms: {invalid}. Valid rooms: {ROOM_IDS}")
        sys.exit(1)

    print("=" * 60)
    print("🔴  Demo: scenario injection")
    print(f"    Scenario: {args.scenario}")
    print(f"    Target rooms: {', '.join(target_rooms)}")
    print("=" * 60)
    print()
    for room_id in target_rooms:
        deteriorate(room_id, args.scenario)
        time.sleep(0.1)

    print()
    print("📊  Watch the Streamlit dashboard (http://localhost:8501)")
    print("    → Risk scores will escalate over ~5 minutes")
    print("    → Alerts will appear in the Active Alerts panel")
    print()
    print("  Run  scripts/demo_clear_alert.py  to acknowledge alerts")
    print("  Run  scripts/demo_normal.py       to restore normal state")


if __name__ == "__main__":
    main()
