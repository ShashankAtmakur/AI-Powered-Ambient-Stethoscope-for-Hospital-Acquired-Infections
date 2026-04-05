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

import random
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


def _scenario_profile(scenario: PatientScenario) -> Dict[str, float]:
    """Return baseline physiology profile for a scenario."""
    if scenario == PatientScenario.PNEUMONIA_LIKE:
        return {
            "br_mean": 27.0,
            "br_std": 2.5,
            "cough_prob": 0.72,
            "wheeze_prob": 0.56,
            "sneeze_prob": 0.10,
            "snore_prob": 0.14,
            "spo2_mean": 90.5,
            "spo2_std": 1.4,
            "temp_mean": 39.0,
            "temp_std": 0.35,
        }
    if scenario == PatientScenario.URI_LIKE:
        return {
            "br_mean": 20.5,
            "br_std": 2.2,
            "cough_prob": 0.58,
            "wheeze_prob": 0.24,
            "sneeze_prob": 0.62,
            "snore_prob": 0.10,
            "spo2_mean": 95.0,
            "spo2_std": 1.0,
            "temp_mean": 38.1,
            "temp_std": 0.30,
        }
    if scenario == PatientScenario.SLEEP_APNEA_LIKE:
        return {
            "br_mean": 10.5,
            "br_std": 2.8,
            "cough_prob": 0.16,
            "wheeze_prob": 0.14,
            "sneeze_prob": 0.05,
            "snore_prob": 0.78,
            "spo2_mean": 92.8,
            "spo2_std": 1.6,
            "temp_mean": 37.1,
            "temp_std": 0.22,
        }
    if scenario == PatientScenario.DETERIORATING:
        return {
            "br_mean": DETN_BREATH_RATE_MEAN,
            "br_std": DETN_BREATH_RATE_STD,
            "cough_prob": DETN_COUGH_PROB,
            "wheeze_prob": DETN_WHEEZE_PROB,
            "sneeze_prob": 0.25,
            "snore_prob": 0.35,
            "spo2_mean": DETN_SPO2_MEAN,
            "spo2_std": DETN_SPO2_STD,
            "temp_mean": DETN_TEMP_MEAN,
            "temp_std": DETN_TEMP_STD,
        }
    return {
        "br_mean": NORMAL_BREATH_RATE_MEAN,
        "br_std": NORMAL_BREATH_RATE_STD,
        "cough_prob": NORMAL_COUGH_PROB,
        "wheeze_prob": NORMAL_WHEEZE_PROB,
        "sneeze_prob": 0.03,
        "snore_prob": 0.04,
        "spo2_mean": NORMAL_SPO2_MEAN,
        "spo2_std": NORMAL_SPO2_STD,
        "temp_mean": NORMAL_TEMP_MEAN,
        "temp_std": NORMAL_TEMP_STD,
    }


def set_scenario(room_id: str, scenario: PatientScenario) -> None:
    """Set the simulated patient scenario for a room."""
    _room_scenarios[room_id] = scenario
    if scenario == PatientScenario.NORMAL:
        _room_detn_progress[room_id] = 0.0
    elif scenario != PatientScenario.DETERIORATING:
        _room_detn_progress[room_id] = 1.0


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
    elif scenario == PatientScenario.NORMAL:
        progress = 0.0
    else:
        progress = 1.0

    p = progress  # shorthand
    target = _scenario_profile(scenario)

    # ── Interpolated physiology parameters ────────────────────────────────────
    br_mean = _lerp(NORMAL_BREATH_RATE_MEAN, target["br_mean"], p)
    br_std = _lerp(NORMAL_BREATH_RATE_STD, target["br_std"], p)
    cough_prob = _lerp(NORMAL_COUGH_PROB, target["cough_prob"], p)
    wheeze_prob = _lerp(NORMAL_WHEEZE_PROB, target["wheeze_prob"], p)
    sneeze_prob = _lerp(0.03, target["sneeze_prob"], p)
    snore_prob = _lerp(0.04, target["snore_prob"], p)
    spo2_mean = _lerp(NORMAL_SPO2_MEAN, target["spo2_mean"], p)
    spo2_std = _lerp(NORMAL_SPO2_STD, target["spo2_std"], p)
    temp_mean = _lerp(NORMAL_TEMP_MEAN, target["temp_mean"], p)
    temp_std = _lerp(NORMAL_TEMP_STD, target["temp_std"], p)

    # ── Sample features ───────────────────────────────────────────────────────
    breath_rate = float(np.clip(np.random.normal(br_mean, br_std), 4.0, 50.0))

    cough_detected = random.random() < cough_prob
    cough_confidence = float(np.clip(np.random.beta(5, 2) * 0.9 + 0.1, 0.0, 1.0)) if cough_detected else 0.0

    # coughs_per_min: direct per-window estimate (window = ~2 s; each cough event
    # represents a detected cough in that window; scaled to /min)
    coughs_per_min = cough_confidence * 10.0 if cough_detected else 0.0
    sneezes_per_min = (
        float(np.clip(np.random.beta(4, 3) * 6.0, 0.0, 12.0))
        if random.random() < sneeze_prob
        else 0.0
    )
    snores_per_min = (
        float(np.clip(np.random.beta(5, 2) * 8.0, 0.0, 18.0))
        if random.random() < snore_prob
        else 0.0
    )

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
        "sneezes_per_min": round(sneezes_per_min, 2),
        "snores_per_min": round(snores_per_min, 2),
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
