"""
shared/schemas.py
Pydantic data-transfer objects shared across all simulator modules.
No audio data or PII is ever stored – only derived acoustic features.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enumerations ──────────────────────────────────────────────────────────────

class PatientScenario(str, Enum):
    """Simulated patient health state controlled by the demo operator."""
    NORMAL = "normal"
    DETERIORATING = "deteriorating"


class AlertSeverity(str, Enum):
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(str, Enum):
    HIGH_COUGH_RATE = "high_cough_rate"
    ABNORMAL_BREATH_RATE = "abnormal_breath_rate"
    LOW_SPO2 = "low_spo2"
    ELEVATED_TEMP = "elevated_temp"
    HAP_RISK_MEDIUM = "hap_risk_medium"
    HAP_RISK_HIGH = "hap_risk_high"
    HAP_RISK_CRITICAL = "hap_risk_critical"


# ── Sensor / edge-ML output ───────────────────────────────────────────────────

class RoomEvent(BaseModel):
    """
    Privacy-safe feature event emitted by the edge-ML layer.
    Contains ONLY derived acoustic/physiological features – never raw audio.
    """
    room_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    scenario: PatientScenario = PatientScenario.NORMAL

    # Acoustic features (derived, not raw audio)
    cough_detected: bool = False
    cough_confidence: float = Field(0.0, ge=0.0, le=1.0)
    coughs_per_min: float = Field(0.0, ge=0.0)
    wheeze_detected: bool = False
    wheeze_confidence: float = Field(0.0, ge=0.0, le=1.0)

    # Respiratory kinematics
    breath_rate_bpm: float = Field(14.0, ge=0.0, le=60.0)
    breath_irregularity: float = Field(0.0, ge=0.0, le=1.0)

    # Environment / vitals proxies
    spo2_pct: float = Field(97.5, ge=80.0, le=100.0)
    temperature_c: float = Field(37.0, ge=35.0, le=42.0)
    ambient_noise_db: float = Field(40.0, ge=0.0)

    # Edge classifier label
    anomaly_label: str = "normal"   # "normal" | "mild" | "moderate" | "severe"
    anomaly_score: float = Field(0.0, ge=0.0, le=1.0)


# ── Backend / alert models ────────────────────────────────────────────────────

class RoomAlert(BaseModel):
    """Alert raised by the backend alert engine for a room."""
    id: Optional[int] = None
    room_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    risk_score: float = Field(0.0, ge=0.0, le=1.0)
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None


class RoomStatus(BaseModel):
    """Snapshot of the latest room state returned by the API."""
    room_id: str
    last_updated: Optional[datetime] = None
    scenario: PatientScenario = PatientScenario.NORMAL
    breath_rate_bpm: float = 14.0
    breath_irregularity: float = 0.0
    coughs_per_min: float = 0.0
    wheeze_detected: bool = False
    spo2_pct: float = 97.5
    temperature_c: float = 37.0
    risk_score: float = 0.0
    alert_level: str = "normal"   # "normal" | "medium" | "high" | "critical"
    active_alerts: list[RoomAlert] = Field(default_factory=list)


class ScenarioChangeRequest(BaseModel):
    """REST payload to change a room's simulated scenario."""
    room_id: str
    scenario: PatientScenario


class AcknowledgeRequest(BaseModel):
    """REST payload to acknowledge an alert."""
    acknowledged_by: str = "nurse"
