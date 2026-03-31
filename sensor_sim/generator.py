"""
sensor_sim/generator.py
Per-room acoustic feature generator.

Simulates the output of a 4-mic MEMS array processed through an edge MCU.
Produces privacy-safe scalar features – NO raw audio is generated, stored,
or transmitted.

Supports two patient scenarios:
  - PatientScenario.NORMAL       – healthy baseline
  - PatientScenario.DETERIORATING – escalating HAP-like pattern
"""

from __future__ import annotations

import math
import random
import time
from datetime import datetime, timezone
from typing import Dict, Any

import numpy as np

from shared.config import (
    NORMAL_BREATH_RATE_MEAN, NORMAL_BREATH_RATE_STD,
    NORMAL_COUGH_PROB, NORMAL_WHEEZE_PROB,
    NORMAL_SPO2_MEAN, NORMAL_SPO2_STD,
    NORMAL_TEMP_MEAN, NORMAL_TEMP_STD,
    DETN_BREATH_RATE_MEAN, DETN_BREATH_RATE_STD,
    DETN_COUGH_PROB, DETN_WHEEZE_PROB,
    DETN_SPO2_MEAN, DETN_SPO2_STD,
    DETN_TEMP_MEAN, DETN_TEMP_STD,
)
from shared.schemas import PatientScenario

# Global scenario store: room_id → PatientScenario
_room_scenarios: Dict[str, PatientScenario] = {}
# Deterioration progression counter per room (0–1 ramp over ~5 min)
_room_detn_progress: Dict[str, float] = {}


def set_scenario(room_id: str, scenario: PatientScenario) -> None:
    """Set the simulated patient scenario for a room."""
    _room_scenarios[room_id] = scenario
    if scenario == PatientScenario.NORMAL:
        _room_detn_progress[room_id] = 0.0


def get_scenario(room_id: str) -> PatientScenario:
    """Get the current scenario for a room (defaults to NORMAL)."""
    return _room_scenarios.get(room_id, PatientScenario.NORMAL)


def generate_features(room_id: str) -> Dict[str, Any]:
    """
    Generate one feature sample for a room.

    Deterioration is modelled as a linear ramp from normal → severe parameters
    over ~5 minutes (150 two-second windows), making the demo graph visually
    compelling.

    Returns a dict suitable for constructing a RoomEvent.
    """
    scenario = get_scenario(room_id)

    # Advance deterioration ramp
    if scenario == PatientScenario.DETERIORATING:
        progress = _room_detn_progress.get(room_id, 0.0)
        progress = min(progress + 1.0 / 150.0, 1.0)   # ~5 min at 2 s intervals
        _room_detn_progress[room_id] = progress
    else:
        progress = 0.0

    p = progress  # shorthand

    # ── Interpolated physiology parameters ────────────────────────────────────
    br_mean = _lerp(NORMAL_BREATH_RATE_MEAN, DETN_BREATH_RATE_MEAN, p)
    br_std = _lerp(NORMAL_BREATH_RATE_STD, DETN_BREATH_RATE_STD, p)
    cough_prob = _lerp(NORMAL_COUGH_PROB, DETN_COUGH_PROB, p)
    wheeze_prob = _lerp(NORMAL_WHEEZE_PROB, DETN_WHEEZE_PROB, p)
    spo2_mean = _lerp(NORMAL_SPO2_MEAN, DETN_SPO2_MEAN, p)
    spo2_std = _lerp(NORMAL_SPO2_STD, DETN_SPO2_STD, p)
    temp_mean = _lerp(NORMAL_TEMP_MEAN, DETN_TEMP_MEAN, p)
    temp_std = _lerp(NORMAL_TEMP_STD, DETN_TEMP_STD, p)

    # ── Sample features ───────────────────────────────────────────────────────
    breath_rate = float(np.clip(np.random.normal(br_mean, br_std), 4.0, 50.0))

    cough_detected = random.random() < cough_prob
    cough_confidence = float(np.clip(np.random.beta(5, 2) * 0.9 + 0.1, 0.0, 1.0)) if cough_detected else 0.0

    # coughs_per_min: direct per-window estimate (window = ~2 s; each cough event
    # represents a detected cough in that window; scaled to /min)
    coughs_per_min = cough_confidence * 10.0 if cough_detected else 0.0

    wheeze_detected = random.random() < wheeze_prob
    wheeze_confidence = float(np.clip(np.random.beta(5, 2) * 0.9 + 0.1, 0.0, 1.0)) if wheeze_detected else 0.0

    spo2 = float(np.clip(np.random.normal(spo2_mean, spo2_std), 80.0, 100.0))
    temperature = float(np.clip(np.random.normal(temp_mean, temp_std), 35.0, 42.0))
    ambient_noise = float(np.clip(np.random.normal(42.0, 5.0), 20.0, 90.0))

    return {
        "room_id": room_id,
        "timestamp": datetime.now(timezone.utc),
        "scenario": scenario,
        "cough_detected": cough_detected,
        "cough_confidence": round(cough_confidence, 4),
        "coughs_per_min": round(coughs_per_min, 2),
        "wheeze_detected": wheeze_detected,
        "wheeze_confidence": round(wheeze_confidence, 4),
        "breath_rate_bpm": round(breath_rate, 2),
        "breath_irregularity": 0.0,   # filled in by classifier
        "spo2_pct": round(spo2, 2),
        "temperature_c": round(temperature, 2),
        "ambient_noise_db": round(ambient_noise, 1),
        "anomaly_label": "normal",
        "anomaly_score": 0.0,
    }


def _lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b at position t ∈ [0, 1]."""
    return a + (b - a) * t
