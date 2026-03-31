"""
backend/app.py
FastAPI application providing:
  - REST endpoints for room status, alerts, scenario control
  - WebSocket endpoint for live dashboard push

Run with::

    uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from shared.config import ROOM_IDS
from shared.schemas import (
    AcknowledgeRequest,
    RoomAlert,
    RoomStatus,
    ScenarioChangeRequest,
    PatientScenario,
)
from backend.database import Database
from backend.aggregator import Aggregator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

# ── App & middleware ───────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Ambient Stethoscope – Backend",
    description=(
        "Privacy-preserving HAP detection backend. "
        "Processes acoustic features only – no raw audio stored."
    ),
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Singletons ────────────────────────────────────────────────────────────────
db = Database()
aggregator = Aggregator(db)

# ── WebSocket connection manager ──────────────────────────────────────────────

class ConnectionManager:
    """Tracks active WebSocket connections and broadcasts messages."""

    def __init__(self) -> None:
        self._connections: List[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        logger.info("WS client connected (%d total)", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.remove(ws)
        logger.info("WS client disconnected (%d total)", len(self._connections))

    async def broadcast(self, data: dict) -> None:
        dead: List[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._connections.remove(ws)


ws_manager = ConnectionManager()


# ── Aggregator callbacks → WebSocket broadcast ────────────────────────────────

async def _broadcast_status(status: dict) -> None:
    await ws_manager.broadcast({"type": "room_status", "data": status})


async def _broadcast_alert(alert: dict) -> None:
    await ws_manager.broadcast({"type": "alert", "data": alert})


# ── App lifecycle ─────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event() -> None:
    loop = asyncio.get_event_loop()
    aggregator.set_event_loop(loop)
    aggregator.on_event(_broadcast_status)
    aggregator.on_alert(_broadcast_alert)
    aggregator.start()
    logger.info("Backend started.  Listening for MQTT events…")

    # Optionally start the sensor simulator in-process (for local demo/dev)
    if os.environ.get("EMBEDDED_SENSOR", "1") == "1":
        from sensor_sim.publisher import SensorSimulator
        from shared.config import SENSOR_PUBLISH_INTERVAL_S
        sim = SensorSimulator(room_ids=ROOM_IDS,
                              interval=SENSOR_PUBLISH_INTERVAL_S)
        sim.start()
        app.state.sensor_sim = sim
        logger.info("Embedded sensor simulator started for rooms: %s", ROOM_IDS)

        # Optionally pre-inject a deteriorating room for demo
        detn_room = os.environ.get("DETERIORATE_ROOM", "")
        if detn_room:
            sim.set_scenario(detn_room,
                             __import__("shared.schemas",
                                        fromlist=["PatientScenario"]).PatientScenario.DETERIORATING)
            logger.info("Pre-injected deterioration for room %s", detn_room)


# ── REST endpoints ────────────────────────────────────────────────────────────

@app.get("/health")
def health_check() -> Dict[str, str]:
    """Health check / liveness probe."""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/rooms", response_model=List[str])
def list_rooms() -> List[str]:
    """Return all configured room IDs."""
    return ROOM_IDS


@app.get("/rooms/{room_id}/status", response_model=RoomStatus)
def get_room_status(room_id: str) -> RoomStatus:
    """Get the latest aggregated status for a room."""
    if room_id not in ROOM_IDS:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")
    return aggregator.get_room_status(room_id)


@app.get("/rooms/{room_id}/timeseries")
def get_timeseries(room_id: str, limit: int = 120) -> List[Dict[str, Any]]:
    """Return the most recent *limit* events for a room (for charts)."""
    if room_id not in ROOM_IDS:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")
    rows = db.get_timeseries(room_id, limit=limit)
    return [dict(row) for row in rows]


@app.get("/alerts", response_model=List[RoomAlert])
def get_all_active_alerts() -> List[RoomAlert]:
    """Return all currently active (unacknowledged) alerts across all rooms."""
    rows = db.get_active_alerts()
    return [
        RoomAlert(
            id=r["id"],
            room_id=r["room_id"],
            timestamp=datetime.fromisoformat(r["timestamp"]),
            alert_type=r["alert_type"],
            severity=r["severity"],
            message=r["message"],
            risk_score=r["risk_score"],
            acknowledged=bool(r["acknowledged"]),
        )
        for r in rows
    ]


@app.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, body: AcknowledgeRequest) -> Dict[str, Any]:
    """Acknowledge an alert."""
    ok = db.acknowledge_alert(alert_id, body.acknowledged_by)
    if not ok:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "acknowledged", "alert_id": alert_id}


@app.post("/rooms/{room_id}/scenario")
def set_scenario(room_id: str, body: ScenarioChangeRequest) -> Dict[str, Any]:
    """
    Change the simulated patient scenario for a room.

    This is the "Simulate Deterioration" trigger used in the demo.
    """
    if room_id not in ROOM_IDS:
        raise HTTPException(status_code=404, detail=f"Room {room_id} not found")
    # Import the generator's set_scenario to affect the running publisher
    from sensor_sim.generator import set_scenario as _set
    _set(room_id, body.scenario)
    logger.info("Room %s scenario → %s", room_id, body.scenario.value)
    return {
        "room_id": room_id,
        "scenario": body.scenario.value,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/summary")
def get_ward_summary() -> Dict[str, Any]:
    """Return a high-level summary of the ward (all rooms)."""
    statuses = [aggregator.get_room_status(rid) for rid in ROOM_IDS]
    critical = [s for s in statuses if s.alert_level == "critical"]
    high = [s for s in statuses if s.alert_level == "high"]
    active_alerts = db.get_active_alerts()
    return {
        "total_rooms": len(ROOM_IDS),
        "critical_rooms": len(critical),
        "high_risk_rooms": len(high),
        "total_active_alerts": len(active_alerts),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for the dashboard.

    Sends live room-status and alert updates as JSON messages::

        {"type": "room_status", "data": {...}}
        {"type": "alert",       "data": {...}}

    On connect, immediately pushes the current status of all rooms.
    """
    await ws_manager.connect(websocket)
    try:
        # Send current state on connect
        for room_id in ROOM_IDS:
            status = aggregator.get_room_status(room_id)
            await websocket.send_json({
                "type": "room_status",
                "data": status.model_dump(mode="json"),
            })
        # Keep alive – just receive pings/pongs
        while True:
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
