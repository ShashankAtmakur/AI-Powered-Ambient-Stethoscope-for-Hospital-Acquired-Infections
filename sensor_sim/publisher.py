"""
sensor_sim/publisher.py
MQTT publisher for simulated room feature events.

Each room runs in its own thread.  The in-process SimpleMQTTClient
(common/simple_broker.py) is used when running in local demo mode;
a real paho-mqtt client can be substituted by setting USE_PAHO=1 env var.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Dict

# Ensure repo root is on the path when running as a script
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from shared.config import (
    MQTT_BROKER, MQTT_PORT, ROOM_IDS, SENSOR_PUBLISH_INTERVAL_S,
    TOPIC_SENSOR,
)
from shared.schemas import RoomEvent, PatientScenario
from sensor_sim.generator import generate_features, set_scenario, get_scenario
from edge_ml.classifier import classify

logger = logging.getLogger(__name__)


def _get_mqtt_client(client_id: str):
    """Return either a paho or simple MQTT client depending on USE_PAHO env."""
    if os.environ.get("USE_PAHO", "0") == "1":
        import paho.mqtt.client as mqtt  # type: ignore
        client = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_start()
        return client, lambda c, t, p: c.publish(t, p)
    else:
        # Use the in-process simple broker (no external deps)
        common_path = os.path.join(_REPO_ROOT, "common")
        if common_path not in sys.path:
            sys.path.insert(0, common_path)
        from simple_broker import SimpleMQTTClient  # type: ignore
        c = SimpleMQTTClient(client_id)
        c.connect(MQTT_BROKER, MQTT_PORT)
        return c, lambda client, t, p: client.publish(t, p)


def _serialize_event(event: RoomEvent) -> str:
    """Serialize a RoomEvent to JSON, converting datetime to ISO string."""
    d = event.model_dump()
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return json.dumps(d)


class RoomPublisher(threading.Thread):
    """Background thread that publishes feature events for a single room."""

    def __init__(self, room_id: str, interval: float = SENSOR_PUBLISH_INTERVAL_S):
        super().__init__(daemon=True, name=f"publisher-{room_id}")
        self.room_id = room_id
        self.interval = interval
        self._stop_event = threading.Event()
        self._client, self._publish = _get_mqtt_client(f"sensor_{room_id}")
        self.topic = TOPIC_SENSOR.format(room_id=room_id)

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        logger.info("[%s] Publisher started (interval=%.1fs)", self.room_id, self.interval)
        while not self._stop_event.is_set():
            try:
                raw_features = generate_features(self.room_id)
                event: RoomEvent = classify(raw_features)
                payload = _serialize_event(event)
                self._publish(self._client, self.topic, payload)
                logger.debug("[%s] Published → %s (score=%.3f)",
                             self.room_id, event.anomaly_label, event.anomaly_score)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[%s] Publish error: %s", self.room_id, exc)
            self._stop_event.wait(self.interval)


class SensorSimulator:
    """
    Manages per-room publishers for the entire simulated ward.

    Usage::

        sim = SensorSimulator()
        sim.start()
        sim.set_scenario("312A", PatientScenario.DETERIORATING)
        ...
        sim.stop()
    """

    def __init__(self, room_ids: list[str] = ROOM_IDS,
                 interval: float = SENSOR_PUBLISH_INTERVAL_S):
        self._publishers: Dict[str, RoomPublisher] = {
            rid: RoomPublisher(rid, interval) for rid in room_ids
        }

    def start(self) -> None:
        for pub in self._publishers.values():
            pub.start()
        logger.info("SensorSimulator started for rooms: %s",
                    list(self._publishers.keys()))

    def stop(self) -> None:
        for pub in self._publishers.values():
            pub.stop()

    def set_scenario(self, room_id: str, scenario: PatientScenario) -> None:
        set_scenario(room_id, scenario)
        logger.info("[%s] Scenario changed → %s", room_id, scenario.value)

    def get_scenario(self, room_id: str) -> PatientScenario:
        return get_scenario(room_id)
