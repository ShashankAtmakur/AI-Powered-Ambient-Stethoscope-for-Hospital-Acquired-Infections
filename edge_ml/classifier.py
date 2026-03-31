"""
edge_ml/classifier.py
Rule-based edge ML classifier that converts raw acoustic feature vectors into
labelled RoomEvent objects.

Privacy guarantee: this module operates exclusively on pre-computed scalar
features.  No audio waveforms, no audio files, and no personally identifiable
information ever enter this module.
"""

from __future__ import annotations

import math
from typing import Dict, Any

from shared.config import (
    NORMAL_BREATH_RATE_MEAN,
    DETN_BREATH_RATE_MEAN,
    ALERT_BREATH_RATE_LOW,
    ALERT_BREATH_RATE_HIGH,
    ALERT_SPO2_LOW,
    ALERT_TEMP_HIGH,
)
from shared.schemas import RoomEvent, PatientScenario
from shared.constants import LABEL_NORMAL, LABEL_MILD, LABEL_MODERATE, LABEL_SEVERE


# ── Scoring weights ───────────────────────────────────────────────────────────
_W_COUGH = 0.30
_W_WHEEZE = 0.20
_W_BREATH = 0.20
_W_SPO2 = 0.20
_W_TEMP = 0.10


def classify(features: Dict[str, Any]) -> RoomEvent:
    """
    Apply rule-based classification to a feature dictionary and return a
    fully-populated RoomEvent.

    Parameters
    ----------
    features:
        Dictionary with keys matching the RoomEvent field names
        (produced by sensor_sim.generator).

    Returns
    -------
    RoomEvent
        The classified event including anomaly_label and anomaly_score.
    """
    event = RoomEvent(**features)

    # ── Sub-scores (each in [0, 1]) ───────────────────────────────────────────
    # Cough contribution
    cough_score: float = min(event.coughs_per_min / 8.0, 1.0) * (
        0.5 + 0.5 * event.cough_confidence
    )

    # Wheeze contribution
    wheeze_score: float = event.wheeze_confidence if event.wheeze_detected else 0.0

    # Breathing rate contribution – distance from normal range
    br = event.breath_rate_bpm
    if br < ALERT_BREATH_RATE_LOW or br > ALERT_BREATH_RATE_HIGH:
        breath_score = min(
            abs(br - NORMAL_BREATH_RATE_MEAN) / 20.0, 1.0
        )
    else:
        # Mild elevation between 18 and 24 still contributes a small score
        deviation = max(br - 18.0, 0.0) / (ALERT_BREATH_RATE_HIGH - 18.0)
        breath_score = 0.3 * deviation

    # SpO2 contribution
    spo2_score: float = max(0.0, (ALERT_SPO2_LOW - event.spo2_pct) / 10.0)

    # Temperature contribution
    temp_score: float = max(0.0, (event.temperature_c - ALERT_TEMP_HIGH) / 3.0)
    temp_score = min(temp_score, 1.0)

    # ── Weighted composite anomaly score ──────────────────────────────────────
    anomaly_score: float = (
        _W_COUGH * cough_score
        + _W_WHEEZE * wheeze_score
        + _W_BREATH * breath_score
        + _W_SPO2 * spo2_score
        + _W_TEMP * temp_score
    )
    anomaly_score = round(min(max(anomaly_score, 0.0), 1.0), 4)

    # ── Label assignment ──────────────────────────────────────────────────────
    if anomaly_score < 0.20:
        label = LABEL_NORMAL
    elif anomaly_score < 0.45:
        label = LABEL_MILD
    elif anomaly_score < 0.70:
        label = LABEL_MODERATE
    else:
        label = LABEL_SEVERE

    event.anomaly_label = label
    event.anomaly_score = anomaly_score

    # ── Breath irregularity: coefficient of variation proxy ───────────────────
    # For the simulator we derive it from how far br deviates from the
    # scenario-specific mean.
    scenario_mean = (
        DETN_BREATH_RATE_MEAN
        if event.scenario == PatientScenario.DETERIORATING
        else NORMAL_BREATH_RATE_MEAN
    )
    event.breath_irregularity = round(
        min(abs(br - scenario_mean) / scenario_mean, 1.0), 3
    )

    return event
