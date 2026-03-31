#!/usr/bin/env python3
"""
dashboard/streamlit_app.py
Streamlit nurse-station dashboard for the AI Ambient Stethoscope simulator.

Run with::

    streamlit run dashboard/streamlit_app.py --server.port 8501

Features
--------
- Live per-room status grid (risk score, vital signs, alert level)
- Trend charts for breath rate, cough rate, SpO₂, temperature
- "Simulate Deterioration" / "Restore Normal" buttons per room
- Active alerts panel with acknowledge buttons
- Auto-refresh every 3 seconds via st.rerun()
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from shared.config import BACKEND_API_URL, ROOM_IDS
from shared.constants import RISK_COLORS, SEVERITY_EMOJI

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HAP Monitor – Nurse Dashboard",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

_API = BACKEND_API_URL.rstrip("/")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _get(path: str, default: Any = None) -> Any:
    try:
        r = requests.get(f"{_API}{path}", timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception:
        return default


def _post(path: str, json: dict = None) -> bool:
    try:
        r = requests.post(f"{_API}{path}", json=json or {}, timeout=3)
        return r.ok
    except Exception:
        return False


def _risk_color(level: str) -> str:
    return RISK_COLORS.get(level, "#95a5a6")


def _level_badge(level: str) -> str:
    labels = {
        "normal": "🟢 Normal",
        "medium": "🟡 Medium",
        "high": "🟠 High",
        "critical": "🔴 Critical",
    }
    return labels.get(level, level)


def _sparkline_data(ts_rows: List[Dict], field: str) -> List[float]:
    return [r.get(field, 0) for r in ts_rows]


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div style='background:#1a2a3a;padding:18px 24px;border-radius:8px;margin-bottom:12px'>
      <h1 style='color:white;margin:0;font-size:1.6rem'>
        🏥 AI-Powered Ambient Stethoscope – Nurse Dashboard
      </h1>
      <p style='color:#adb5bd;margin:4px 0 0'>
        Privacy-preserving HAP detection · Features only · No audio stored
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Ward summary bar ──────────────────────────────────────────────────────────
summary = _get("/summary", {})
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Rooms", summary.get("total_rooms", len(ROOM_IDS)))
c2.metric("🔴 Critical", summary.get("critical_rooms", 0))
c3.metric("🟠 High Risk", summary.get("high_risk_rooms", 0))
c4.metric("🔔 Active Alerts", summary.get("total_active_alerts", 0))

st.divider()

# ── Active alerts panel ───────────────────────────────────────────────────────
with st.expander("🔔 Active Alerts", expanded=True):
    alerts: List[Dict] = _get("/alerts", [])
    if not alerts:
        st.success("No active alerts – all rooms nominal.")
    else:
        for a in alerts:
            sev = a.get("severity", "medium")
            emoji = SEVERITY_EMOJI.get(sev, "🔔")
            col_a, col_b = st.columns([9, 1])
            with col_a:
                st.markdown(
                    f"<div style='background:{_risk_color(sev if sev != 'medium' else 'medium')}20;"
                    f"border-left:4px solid {_risk_color(sev if sev != 'medium' else 'medium')};"
                    f"padding:8px 12px;border-radius:4px;margin:4px 0'>"
                    f"{emoji} <b>Room {a['room_id']}</b> &nbsp;|&nbsp; "
                    f"{a.get('message','')} "
                    f"<small style='color:#666'>({a.get('timestamp','')[:19]})</small>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            with col_b:
                if st.button("✓ Ack", key=f"ack_{a['id']}"):
                    _post(f"/alerts/{a['id']}/acknowledge",
                          {"acknowledged_by": "nurse_dashboard"})
                    st.rerun()

st.divider()

# ── Room grid ─────────────────────────────────────────────────────────────────
st.subheader("📊 Room Status Grid")
COLS = 3
grid_cols = st.columns(COLS)

for idx, room_id in enumerate(ROOM_IDS):
    col = grid_cols[idx % COLS]
    with col:
        status: Dict = _get(f"/rooms/{room_id}/status", {})
        level = status.get("alert_level", "normal")
        risk = status.get("risk_score", 0.0)
        br = status.get("breath_rate_bpm", 0.0)
        cpm = status.get("coughs_per_min", 0.0)
        spo2 = status.get("spo2_pct", 0.0)
        temp = status.get("temperature_c", 0.0)
        scenario = status.get("scenario", "normal")
        is_detn = scenario == "deteriorating"

        border = _risk_color(level)
        st.markdown(
            f"""<div style='border:2px solid {border};border-radius:8px;
            padding:12px;margin-bottom:8px'>
            <h3 style='margin:0 0 6px;color:{border}'>
              Room {room_id} &nbsp; {_level_badge(level)}
            </h3>
            <table style='width:100%;font-size:.9rem'>
              <tr><td>🫁 Breath Rate</td><td><b>{br:.1f} bpm</b></td></tr>
              <tr><td>💨 Coughs/min</td><td><b>{cpm:.1f}</b></td></tr>
              <tr><td>🩸 SpO₂</td>       <td><b>{spo2:.1f}%</b></td></tr>
              <tr><td>🌡 Temperature</td><td><b>{temp:.1f}°C</b></td></tr>
              <tr><td>📊 Risk Score</td> <td><b>{risk:.2f}</b></td></tr>
            </table>
            </div>""",
            unsafe_allow_html=True,
        )

        # Scenario control buttons
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button(
                "🔴 Deteriorate",
                key=f"detn_{room_id}",
                disabled=is_detn,
                use_container_width=True,
            ):
                _post(
                    f"/rooms/{room_id}/scenario",
                    {"room_id": room_id, "scenario": "deteriorating"},
                )
                st.rerun()
        with btn_col2:
            if st.button(
                "🟢 Restore",
                key=f"norm_{room_id}",
                disabled=not is_detn,
                use_container_width=True,
            ):
                _post(
                    f"/rooms/{room_id}/scenario",
                    {"room_id": room_id, "scenario": "normal"},
                )
                st.rerun()

st.divider()

# ── Trend charts ──────────────────────────────────────────────────────────────
st.subheader("📈 Trend Charts")
selected_room = st.selectbox("Select room for detailed trends", ROOM_IDS)

ts_rows: List[Dict] = _get(f"/rooms/{selected_room}/timeseries?limit=120", [])

if ts_rows:
    import pandas as pd

    df = pd.DataFrame(ts_rows)
    # Ensure timestamp column
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp").sort_index()

    chart_cols = st.columns(2)
    with chart_cols[0]:
        st.markdown("**🫁 Breathing Rate (bpm)**")
        if "breath_rate_bpm" in df.columns:
            st.line_chart(df["breath_rate_bpm"])
        st.markdown("**💨 Coughs per Minute**")
        if "coughs_per_min" in df.columns:
            st.area_chart(df["coughs_per_min"])
    with chart_cols[1]:
        st.markdown("**🩸 SpO₂ (%)**")
        if "spo2_pct" in df.columns:
            st.line_chart(df["spo2_pct"])
        st.markdown("**📊 Anomaly Score**")
        if "anomaly_score" in df.columns:
            st.area_chart(df["anomaly_score"])
else:
    st.info("No timeseries data yet – start the sensor simulator.")

# ── Auto-refresh ──────────────────────────────────────────────────────────────
st.caption(
    f"🔄 Auto-refreshing every 3 s · Last update: {datetime.now().strftime('%H:%M:%S')}"
)
time.sleep(3)
st.rerun()
