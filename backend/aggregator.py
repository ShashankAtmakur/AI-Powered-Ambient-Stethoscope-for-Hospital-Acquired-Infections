"""
backend/aggregator.py
MQTT subscriber that receives sensor events, stores them in SQLite,
runs the alert engine, and broadcasts updates over WebSocket.

Runs as a background thread started by the FastAPI app.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
from datetime import datetime, timezone
from statistics import mean
from typing import Callable, Dict, Optional

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from shared.config import MQTT_BROKER, MQTT_PORT, ROOM_IDS, RISK_WINDOW_S
from shared.schemas import RoomAlert, RoomEvent, RoomStatus, PatientScenario
from backend.database import Database
from backend.alert_engine import AlertEngine, RoomBuffer

logger = logging.getLogger(__name__)

DISEASE_PREDICTION_WINDOW_SIZE = 30
DISEASE_NONE = "none"
DISEASE_PNEUMONIA = "pneumonia"
DISEASE_URI = "upper_respiratory_infection"
DISEASE_SLEEP_APNEA = "sleep_apnea"

# Heuristic disease-probability model weights/thresholds
_PNEUMONIA_RISK_W = 0.45
_PNEUMONIA_COUGH_W = 0.20
_PNEUMONIA_SPO2_W = 0.20
_PNEUMONIA_TEMP_W = 0.15
_PNEUMONIA_COUGH_SCALE = 6.0
_PNEUMONIA_SPO2_LOW = 94.0
_PNEUMONIA_SPO2_SCALE = 6.0
_PNEUMONIA_TEMP_HIGH = 38.0
_PNEUMONIA_TEMP_SCALE = 2.0

_URI_SNEEZE_W = 0.35
_URI_COUGH_W = 0.30
_URI_TEMP_W = 0.20
_URI_RISK_W = 0.15
_URI_SNEEZE_SCALE = 4.0
_URI_COUGH_SCALE = 5.0
_URI_TEMP_HIGH = 37.5
_URI_TEMP_SCALE = 2.0

_SLEEP_APNEA_SNORE_W = 0.55
_SLEEP_APNEA_SPO2_W = 0.30
_SLEEP_APNEA_BREATH_IRREGULARITY_W = 0.15
_SLEEP_APNEA_SNORE_SCALE = 8.0
_SLEEP_APNEA_SPO2_LOW = 95.0
_SLEEP_APNEA_SPO2_SCALE = 7.0
_SLEEP_APNEA_BREATH_IRREGULARITY_SCALE = 1.0


class Aggregator(threading.Thread):
    """
    Background thread that:
      1. Subscribes to hospital/rooms/+/events via MQTT
      2. Inserts each event into SQLite
      3. Runs the alert engine
      4. Calls registered broadcast callbacks for WebSocket push
    """

    def __init__(self, db: Database) -> None:
        super().__init__(daemon=True, name="aggregator")
        self.db = db
        self.engine = AlertEngine()
        self._buffers: Dict[str, RoomBuffer] = {
            rid: RoomBuffer(rid) for rid in ROOM_IDS
        }
        self._on_event_callbacks: list[Callable] = []
        self._on_alert_callbacks: list[Callable] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ── Callback registration ─────────────────────────────────────────────────

    def on_event(self, fn: Callable) -> None:
        """Register a callback invoked on every new event (room_status dict)."""
        self._on_event_callbacks.append(fn)

    def on_alert(self, fn: Callable) -> None:
        """Register a callback invoked on every new alert (alert dict)."""
        self._on_alert_callbacks.append(fn)

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    # ── Public helpers used by the REST API ───────────────────────────────────

    def get_room_status(self, room_id: str) -> RoomStatus:
        buf = self._buffers.get(room_id)
        if buf is None:
            return RoomStatus(room_id=room_id)
        recent = buf.recent(RISK_WINDOW_S)
        if not recent:
            latest = buf.latest()
            if latest is None:
                return RoomStatus(room_id=room_id)
            recent = [latest]

        risk = self.engine.compute_risk_score(recent)
        latest = buf.latest()
        assert latest is not None
        disease_probabilities = self._predict_disease_probabilities(recent, risk)
        likely_disease = (
            max(disease_probabilities, key=disease_probabilities.get)
            if disease_probabilities
            else DISEASE_NONE
        )
        affected = likely_disease != DISEASE_NONE

        from shared.config import (
            ALERT_RISK_SCORE_CRITICAL, ALERT_RISK_SCORE_HIGH,
            ALERT_RISK_SCORE_MEDIUM,
        )
        if risk >= ALERT_RISK_SCORE_CRITICAL:
            alert_level = "critical"
        elif risk >= ALERT_RISK_SCORE_HIGH:
            alert_level = "high"
        elif risk >= ALERT_RISK_SCORE_MEDIUM:
            alert_level = "medium"
        else:
            alert_level = "normal"

        active = self.db.get_active_alerts(room_id)
        active_alerts = [
            RoomAlert(
                id=row["id"],
                room_id=row["room_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                alert_type=row["alert_type"],
                severity=row["severity"],
                message=row["message"],
                risk_score=row["risk_score"],
                acknowledged=bool(row["acknowledged"]),
            )
            for row in active
        ]

        return RoomStatus(
            room_id=room_id,
            last_updated=latest.timestamp,
            scenario=latest.scenario,
            breath_rate_bpm=latest.breath_rate_bpm,
            breath_irregularity=latest.breath_irregularity,
            coughs_per_min=latest.coughs_per_min,
            sneezes_per_min=latest.sneezes_per_min,
            snores_per_min=latest.snores_per_min,
            wheeze_detected=latest.wheeze_detected,
            spo2_pct=latest.spo2_pct,
            temperature_c=latest.temperature_c,
            risk_score=risk,
            alert_level=alert_level,
            disease_probabilities=disease_probabilities,
            likely_disease=likely_disease,
            affected=affected,
            active_alerts=active_alerts,
        )

    def _predict_disease_probabilities(
        self, events: list[RoomEvent], risk: float
    ) -> dict[str, float]:
        """
        Produce heuristic per-room disease likelihoods from recent event patterns.

        This is a lightweight rules-based model intended for demo/triage display,
        not a diagnostic model. It combines signal intensity (cough/sneeze/snore),
        oxygen saturation, temperature, breathing irregularity, and the existing
        room risk score into bounded per-disease probabilities in [0, 1].
        The "none" score is a simplified complement of the strongest disease
        signal (not a normalized mutually-exclusive probability distribution).
        """
        if not events:
            return {
                DISEASE_NONE: 1.0,
                DISEASE_PNEUMONIA: 0.0,
                DISEASE_URI: 0.0,
                DISEASE_SLEEP_APNEA: 0.0,
            }
        window = (
            events[-DISEASE_PREDICTION_WINDOW_SIZE:]
            if len(events) > DISEASE_PREDICTION_WINDOW_SIZE
            else events
        )
        avg_cough = mean(e.coughs_per_min for e in window)
        avg_sneeze = mean(e.sneezes_per_min for e in window)
        avg_snore = mean(e.snores_per_min for e in window)
        avg_spo2 = mean(e.spo2_pct for e in window)
        avg_temp = mean(e.temperature_c for e in window)
        avg_breath_irregularity = mean(e.breath_irregularity for e in window)

        pneumonia = min(
            1.0,
            _PNEUMONIA_RISK_W * risk
            + _PNEUMONIA_COUGH_W * min(avg_cough / _PNEUMONIA_COUGH_SCALE, 1.0)
            + _PNEUMONIA_SPO2_W
            * min(max(_PNEUMONIA_SPO2_LOW - avg_spo2, 0.0) / _PNEUMONIA_SPO2_SCALE, 1.0)
            + _PNEUMONIA_TEMP_W
            * min(max(avg_temp - _PNEUMONIA_TEMP_HIGH, 0.0) / _PNEUMONIA_TEMP_SCALE, 1.0),
        )
        upper_respiratory_infection = min(
            1.0,
            _URI_SNEEZE_W * min(avg_sneeze / _URI_SNEEZE_SCALE, 1.0)
            + _URI_COUGH_W * min(avg_cough / _URI_COUGH_SCALE, 1.0)
            + _URI_TEMP_W * min(max(avg_temp - _URI_TEMP_HIGH, 0.0) / _URI_TEMP_SCALE, 1.0)
            + _URI_RISK_W * risk,
        )
        sleep_apnea = min(
            1.0,
            _SLEEP_APNEA_SNORE_W * min(avg_snore / _SLEEP_APNEA_SNORE_SCALE, 1.0)
            + _SLEEP_APNEA_SPO2_W
            * min(max(_SLEEP_APNEA_SPO2_LOW - avg_spo2, 0.0) / _SLEEP_APNEA_SPO2_SCALE, 1.0)
            + _SLEEP_APNEA_BREATH_IRREGULARITY_W
            * min(
                max(avg_breath_irregularity, 0.0)
                / _SLEEP_APNEA_BREATH_IRREGULARITY_SCALE,
                1.0,
            ),
        )
        disease_peak = max(pneumonia, upper_respiratory_infection, sleep_apnea)
        none = max(0.0, 1.0 - disease_peak)
        return {
            DISEASE_NONE: round(none, 4),
            DISEASE_PNEUMONIA: round(pneumonia, 4),
            DISEASE_URI: round(upper_respiratory_infection, 4),
            DISEASE_SLEEP_APNEA: round(sleep_apnea, 4),
        }

    # ── MQTT handling ─────────────────────────────────────────────────────────

    def run(self) -> None:
        """Subscribe to MQTT and process incoming events."""
        client, loop_fn = self._make_client()
        client.subscribe("hospital/rooms/+/events")
        logger.info("Aggregator subscribed to hospital/rooms/+/events")
        loop_fn(client)

    def _process_payload(self, payload: str) -> None:
        try:
            data = json.loads(payload)
            # Normalise timestamp: accept ISO strings with or without timezone
            ts = data.get("timestamp")
            if isinstance(ts, str):
                # Python 3.11+ handles Z suffix natively; for older versions strip it
                ts_clean = ts.rstrip("Z")
                try:
                    dt = datetime.fromisoformat(ts_clean)
                except ValueError:
                    dt = datetime.now(timezone.utc)
                # Make timezone-aware if naive
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                data["timestamp"] = dt
            event = RoomEvent(**data)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to parse event: %s – %s", exc, payload[:200])
            return

        # Ensure buffer exists for this room
        if event.room_id not in self._buffers:
            self._buffers[event.room_id] = RoomBuffer(event.room_id)

        buf = self._buffers[event.room_id]
        buf.push(event)
        self.db.insert_event(event)

        # Alert engine
        new_alerts = self.engine.evaluate(buf)
        for alert in new_alerts:
            alert_id = self.db.insert_alert(alert)
            alert.id = alert_id
            logger.warning("🚨 [%s] %s %s", event.room_id,
                           alert.severity.value.upper(), alert.message)
            self._fire_callbacks(self._on_alert_callbacks,
                                 alert.model_dump(mode="json"))

        # Fire event callbacks (room status)
        status = self.get_room_status(event.room_id)
        self._fire_callbacks(self._on_event_callbacks,
                             status.model_dump(mode="json"))

    def _fire_callbacks(self, callbacks: list[Callable], data: dict) -> None:
        for fn in callbacks:
            try:
                if self._loop and self._loop.is_running():
                    asyncio.run_coroutine_threadsafe(fn(data), self._loop)
                else:
                    fn(data)
            except Exception as exc:  # noqa: BLE001
                logger.debug("Callback error: %s", exc)

    def _make_client(self):
        """Return (client, loop_fn) for in-process or paho MQTT."""
        if os.environ.get("USE_PAHO", "0") == "1":
            import paho.mqtt.client as mqtt  # type: ignore

            def on_message(client, userdata, msg):
                self._process_payload(msg.payload.decode())

            client = mqtt.Client(client_id="aggregator", protocol=mqtt.MQTTv311)
            client.on_message = on_message
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)

            def _loop(c):
                c.loop_forever()

            return client, _loop
        else:
            common_path = os.path.join(_REPO_ROOT, "common")
            if common_path not in sys.path:
                sys.path.insert(0, common_path)
            from simple_broker import SimpleMQTTClient  # type: ignore

            client = SimpleMQTTClient("aggregator")
            client.on_message = lambda c, u, msg: self._process_payload(
                msg.payload if isinstance(msg.payload, str) else msg.payload.decode()
            )
            client.connect(MQTT_BROKER, MQTT_PORT)
            client.subscribe("hospital/rooms/+/events")

            def _loop(c):
                c.loop_forever()

            return client, _loop
