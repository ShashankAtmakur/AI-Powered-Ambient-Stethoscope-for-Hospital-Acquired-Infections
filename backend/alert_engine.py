"""
backend/alert_engine.py
Risk-scoring and alert-generation logic.

The engine maintains a short rolling window of events per room and computes a
composite HAP risk score from:
  - Recent cough rate (coughs/min)
  - Breath rate deviation from normal
  - Breath irregularity
  - SpO2 depression
  - Temperature elevation
  - Edge classifier anomaly score
"""

from __future__ import annotations

import logging
import os
import sys
from collections import deque
from datetime import datetime, timezone
from statistics import mean
from typing import Deque, Dict, List, Optional

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from shared.config import (
    ALERT_BREATH_RATE_HIGH, ALERT_BREATH_RATE_LOW,
    ALERT_COUGHS_PER_MIN_THRESHOLD, ALERT_RISK_SCORE_CRITICAL,
    ALERT_RISK_SCORE_HIGH, ALERT_RISK_SCORE_MEDIUM, ALERT_SPO2_LOW,
    ALERT_TEMP_HIGH, NORMAL_BREATH_RATE_MEAN, RISK_WINDOW_S,
)
from shared.schemas import AlertSeverity, AlertType, RoomAlert, RoomEvent

logger = logging.getLogger(__name__)

# Max events to keep in memory per room (circular buffer)
_MAX_BUFFER = 300


class RoomBuffer:
    """Circular buffer of recent RoomEvent objects for one room."""

    def __init__(self, room_id: str) -> None:
        self.room_id = room_id
        self._events: Deque[RoomEvent] = deque(maxlen=_MAX_BUFFER)

    def push(self, event: RoomEvent) -> None:
        self._events.append(event)

    def recent(self, window_s: int = RISK_WINDOW_S) -> List[RoomEvent]:
        cutoff = (datetime.now(timezone.utc).timestamp() - window_s)
        return [
            e for e in self._events
            if e.timestamp.timestamp() >= cutoff
        ]

    def latest(self) -> Optional[RoomEvent]:
        return self._events[-1] if self._events else None


class AlertEngine:
    """
    Stateless risk scorer and alert generator.

    Call ``evaluate(buffer)`` after each new event is pushed; it returns
    a (possibly empty) list of new RoomAlert objects to be stored and
    broadcast.
    """

    # Track last-raised alert per (room_id, alert_type) to avoid storms
    def __init__(self) -> None:
        self._last_alert: Dict[tuple, datetime] = {}
        self._cooldown_s: int = 60  # minimum seconds between same-type alerts

    def compute_risk_score(self, events: List[RoomEvent]) -> float:
        """
        Compute a composite HAP risk score in [0, 1] from a list of recent events.

        Uses only the most recent 30 events (≈60 s at 2 s interval) to give
        a responsive real-time score that reflects the current patient state
        rather than a diluted historical average.

        Higher is worse.
        """
        if not events:
            return 0.0

        # Focus on the most recent slice for responsiveness
        window = events[-30:] if len(events) > 30 else events

        # Averages over the window
        avg_coughs_pm = mean(e.coughs_per_min for e in window)
        avg_br = mean(e.breath_rate_bpm for e in window)
        avg_irr = mean(e.breath_irregularity for e in window)
        avg_spo2 = mean(e.spo2_pct for e in window)
        avg_temp = mean(e.temperature_c for e in window)
        avg_anomaly = mean(e.anomaly_score for e in window)
        wheeze_frac = sum(1 for e in window if e.wheeze_detected) / len(window)

        # Sub-scores (each 0–1)
        cough_s = min(avg_coughs_pm / 6.0, 1.0)   # saturates at 6 coughs/min

        # breath rate: penalise high (>24) and low (<8) equally
        if avg_br > ALERT_BREATH_RATE_HIGH:
            br_s = min((avg_br - ALERT_BREATH_RATE_HIGH) / 8.0, 1.0)
        elif avg_br < ALERT_BREATH_RATE_LOW:
            br_s = min((ALERT_BREATH_RATE_LOW - avg_br) / 4.0, 1.0)
        else:
            br_s = max(0.0, (avg_br - 18.0) / 6.0)   # mild elevation

        irr_s = min(avg_irr, 1.0)
        spo2_s = min(max(0.0, (ALERT_SPO2_LOW - avg_spo2) / 6.0), 1.0)
        temp_s = min(max(0.0, (avg_temp - ALERT_TEMP_HIGH) / 2.0), 1.0)
        wheeze_s = wheeze_frac

        # Weighted composite
        score = (
            0.25 * cough_s
            + 0.20 * br_s
            + 0.10 * irr_s
            + 0.25 * spo2_s
            + 0.10 * temp_s
            + 0.05 * wheeze_s
            + 0.05 * avg_anomaly
        )
        return round(min(score, 1.0), 4)

    def evaluate(self, buffer: RoomBuffer) -> List[RoomAlert]:
        """
        Evaluate the current buffer state and return new alerts to raise.
        """
        recent = buffer.recent()
        if not recent:
            return []

        risk = self.compute_risk_score(recent)
        # Use recent-30 slice for metric checks too
        window = recent[-30:] if len(recent) > 30 else recent
        latest = buffer.latest()
        assert latest is not None
        alerts: List[RoomAlert] = []
        now = datetime.now(timezone.utc)

        # ── Per-metric alerts ─────────────────────────────────────────────────
        avg_coughs_pm = mean(e.coughs_per_min for e in window)
        avg_br = mean(e.breath_rate_bpm for e in window)
        avg_spo2 = mean(e.spo2_pct for e in window)
        avg_temp = mean(e.temperature_c for e in window)

        if avg_coughs_pm >= ALERT_COUGHS_PER_MIN_THRESHOLD:
            alerts.append(self._make(
                buffer.room_id, AlertType.HIGH_COUGH_RATE, AlertSeverity.HIGH,
                f"Elevated cough rate: {avg_coughs_pm:.1f} coughs/min "
                f"(threshold {ALERT_COUGHS_PER_MIN_THRESHOLD})",
                risk,
            ))

        if avg_br < ALERT_BREATH_RATE_LOW or avg_br > ALERT_BREATH_RATE_HIGH:
            alerts.append(self._make(
                buffer.room_id, AlertType.ABNORMAL_BREATH_RATE, AlertSeverity.HIGH,
                f"Abnormal breathing rate: {avg_br:.1f} bpm "
                f"(normal {ALERT_BREATH_RATE_LOW}–{ALERT_BREATH_RATE_HIGH})",
                risk,
            ))

        if avg_spo2 < ALERT_SPO2_LOW:
            alerts.append(self._make(
                buffer.room_id, AlertType.LOW_SPO2, AlertSeverity.CRITICAL,
                f"Low SpO₂: {avg_spo2:.1f}% (threshold {ALERT_SPO2_LOW}%)",
                risk,
            ))

        if avg_temp >= ALERT_TEMP_HIGH:
            alerts.append(self._make(
                buffer.room_id, AlertType.ELEVATED_TEMP, AlertSeverity.MEDIUM,
                f"Elevated temperature: {avg_temp:.1f}°C "
                f"(threshold {ALERT_TEMP_HIGH}°C)",
                risk,
            ))

        # ── HAP risk-score composite alerts ───────────────────────────────────
        if risk >= ALERT_RISK_SCORE_CRITICAL:
            alerts.append(self._make(
                buffer.room_id, AlertType.HAP_RISK_CRITICAL, AlertSeverity.CRITICAL,
                f"🚨 Critical HAP risk score: {risk:.2f} – immediate review required",
                risk,
            ))
        elif risk >= ALERT_RISK_SCORE_HIGH:
            alerts.append(self._make(
                buffer.room_id, AlertType.HAP_RISK_HIGH, AlertSeverity.HIGH,
                f"⚠️  High HAP risk score: {risk:.2f} – escalating respiratory distress",
                risk,
            ))
        elif risk >= ALERT_RISK_SCORE_MEDIUM:
            alerts.append(self._make(
                buffer.room_id, AlertType.HAP_RISK_MEDIUM, AlertSeverity.MEDIUM,
                f"🔔 Moderate HAP risk score: {risk:.2f} – monitor closely",
                risk,
            ))

        # Filter out same-type alerts raised too recently (cooldown)
        filtered: List[RoomAlert] = []
        for a in alerts:
            key = (buffer.room_id, a.alert_type)
            last = self._last_alert.get(key)
            if last is None or (now - last).total_seconds() >= self._cooldown_s:
                self._last_alert[key] = now
                filtered.append(a)

        return filtered

    @staticmethod
    def _make(
        room_id: str,
        alert_type: AlertType,
        severity: AlertSeverity,
        message: str,
        risk_score: float,
    ) -> RoomAlert:
        return RoomAlert(
            room_id=room_id,
            timestamp=datetime.now(timezone.utc),
            alert_type=alert_type,
            severity=severity,
            message=message,
            risk_score=risk_score,
        )
