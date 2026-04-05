#!/usr/bin/env python3
"""
scripts/demo_multidisease.py
Assign different disease-like scenarios across rooms in one command.

Usage::

    python scripts/demo_multidisease.py
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

_SCENARIO_CYCLE = [
    "pneumonia_like",
    "uri_like",
    "sleep_apnea_like",
    "deteriorating",
]


def apply_scenario(room_id: str, scenario: str) -> bool:
    try:
        response = requests.post(
            f"{API}/rooms/{room_id}/scenario",
            json={"room_id": room_id, "scenario": scenario},
            timeout=5,
        )
    except requests.RequestException as exc:
        print(f"  [error] {room_id}: {exc}")
        return False

    if response.ok:
        print(f"  [ok] {room_id} -> {scenario}")
        return True

    print(f"  [warn] {room_id}: {response.status_code} {response.text}")
    return False


def main() -> None:
    print("=" * 60)
    print("Multi-disease room simulation")
    print("=" * 60)

    successes = 0
    for idx, room_id in enumerate(ROOM_IDS):
        scenario = _SCENARIO_CYCLE[idx % len(_SCENARIO_CYCLE)]
        if apply_scenario(room_id, scenario):
            successes += 1
        time.sleep(0.1)

    print()
    print(f"Applied scenarios to {successes}/{len(ROOM_IDS)} rooms")
    print("Open dashboard at http://localhost:8501 to compare disease probabilities.")


if __name__ == "__main__":
    main()
