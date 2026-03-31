#!/usr/bin/env python3
"""
sensor_sim/main.py
Entry point for the Sensor Node Simulator.

Starts per-room MQTT publishers for all configured rooms.
Run with::

    python -m sensor_sim.main
    # or
    python sensor_sim/main.py

Set DETERIORATE_ROOM env var to trigger immediate deterioration on a room::

    DETERIORATE_ROOM=312A python -m sensor_sim.main
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from shared.config import ROOM_IDS, SENSOR_PUBLISH_INTERVAL_S
from shared.schemas import PatientScenario
from sensor_sim.publisher import SensorSimulator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    sim = SensorSimulator(room_ids=ROOM_IDS, interval=SENSOR_PUBLISH_INTERVAL_S)
    sim.start()

    # Optional: immediately deteriorate a room for demo
    detn_room = os.environ.get("DETERIORATE_ROOM", "")
    if detn_room:
        sim.set_scenario(detn_room, PatientScenario.DETERIORATING)
        logger.info("🔴 Deterioration injected for room %s", detn_room)

    print("=" * 60)
    print("🎙️  Sensor Simulator running")
    print(f"   Rooms: {', '.join(ROOM_IDS)}")
    print(f"   Interval: {SENSOR_PUBLISH_INTERVAL_S}s per room")
    print("   Press Ctrl+C to stop.")
    print("=" * 60)

    def _shutdown(sig, frame):  # noqa: ANN001
        print("\nShutting down sensor simulator…")
        sim.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
