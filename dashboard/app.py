#!/usr/bin/env python3
"""
AI-Powered Ambient Stethoscope - Nurse Dashboard
Web application for monitoring hospital rooms and alerts
"""

from flask import Flask, render_template, jsonify
import sqlite3
import json
from datetime import datetime, timedelta
# import paho.mqtt.client as mqtt
import threading
import sys
import os
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, "common"))
from simple_broker import SimpleMQTTClient
from shared.config import DB_PATH

app = Flask(__name__)

class DashboardData:
    def __init__(self):
        self.db_path = DB_PATH
        self.alerts = []  # Cache active alerts

        # MQTT setup for real-time alerts
        self.client = SimpleMQTTClient("dashboard")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect("localhost", 1883)
        self.client.subscribe("hospital/alerts/+")
        # Start listening in background
        threading.Thread(target=self.client.loop_forever, daemon=True).start()

    def on_connect(self, client, userdata, flags, rc):
        client.subscribe("hospital/alerts/+")

    def on_message(self, client, userdata, msg):
        """Handle incoming alerts"""
        try:
            alert = json.loads(msg.payload.decode())
            self.alerts.append(alert)
            # Keep only recent alerts
            cutoff = datetime.now() - timedelta(hours=24)
            self.alerts = [a for a in self.alerts if datetime.fromisoformat(a['timestamp']) > cutoff]
        except Exception as e:
            print(f"Error processing alert: {e}")

    def get_room_data(self, room_id):
        """Get recent data for a room"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT timestamp, cough_detected, cough_confidence, breathing_rate
                FROM respiratory_data
                WHERE room_id = ?
                ORDER BY timestamp DESC
                LIMIT 100
            ''', (room_id,))
            rows = cursor.fetchall()

        data = []
        for row in rows:
            data.append({
                'timestamp': row[0],
                'cough_detected': bool(row[1]),
                'cough_confidence': row[2],
                'breathing_rate': row[3]
            })
        return data[::-1]  # Reverse to chronological order

    def get_all_rooms(self):
        """Get list of all rooms with recent activity"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT DISTINCT room_id
                FROM respiratory_data
                ORDER BY room_id
            ''')
            return [row[0] for row in cursor.fetchall()]

    def get_active_alerts(self):
        """Get active alerts"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT * FROM alerts
                WHERE acknowledged = FALSE
                ORDER BY timestamp DESC
            ''')
            alerts = []
            for row in cursor:
                alerts.append({
                    'id': row[0],
                    'timestamp': row[1],
                    'room_id': row[2],
                    'patient_id': row[3],
                    'alert_type': row[4],
                    'severity': row[5],
                    'message': row[6],
                    'acknowledged': bool(row[7])
                })
            return alerts

dashboard_data = DashboardData()

@app.route('/')
def index():
    """Main dashboard page"""
    rooms = dashboard_data.get_all_rooms()
    return render_template('index.html', rooms=rooms)

@app.route('/api/room/<room_id>')
def get_room_api(room_id):
    """API endpoint for room data"""
    data = dashboard_data.get_room_data(room_id)
    return jsonify(data)

@app.route('/api/alerts')
def get_alerts_api():
    """API endpoint for active alerts"""
    alerts = dashboard_data.get_active_alerts()
    return jsonify(alerts)

@app.route('/api/alerts/<int:alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    """Acknowledge an alert"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('UPDATE alerts SET acknowledged = TRUE WHERE id = ?', (alert_id,))
        conn.commit()
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)