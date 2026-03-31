#!/usr/bin/env python3
"""
AI-Powered Ambient Stethoscope - Hospital Server
Handles MQTT communication, data storage, and alert processing
"""

import time
import json
import sqlite3
# import paho.mqtt.client as mqtt
from datetime import datetime, timedelta
import threading
import numpy as np
import sys
sys.path.append('/workspaces/AI-Powered-Ambient-Stethoscope-for-Hospital-Acquired-Infections/common')
from simple_broker import SimpleMQTTClient

# Configuration
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
DB_PATH = "/workspaces/AI-Powered-Ambient-Stethoscope-for-Hospital-Acquired-Infections/server/hospital_data.db"

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize database tables"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS respiratory_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    room_id TEXT,
                    patient_id TEXT,
                    cough_detected BOOLEAN,
                    cough_confidence REAL,
                    breathing_rate REAL,
                    audio_features TEXT
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    room_id TEXT,
                    patient_id TEXT,
                    alert_type TEXT,
                    severity TEXT,
                    message TEXT,
                    acknowledged BOOLEAN DEFAULT FALSE
                )
            ''')
            conn.commit()

    def store_respiratory_data(self, data):
        """Store respiratory monitoring data"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO respiratory_data
                (timestamp, room_id, patient_id, cough_detected, cough_confidence, breathing_rate, audio_features)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['timestamp'],
                data['room_id'],
                data['patient_id'],
                data['cough_detected'],
                data['cough_confidence'],
                data['breathing_rate'],
                json.dumps(data['audio_features'])
            ))
            conn.commit()

    def get_recent_data(self, room_id, hours=1):
        """Get recent data for a room"""
        cutoff = datetime.now() - timedelta(hours=hours)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT * FROM respiratory_data
                WHERE room_id = ? AND timestamp > ?
                ORDER BY timestamp DESC
            ''', (room_id, cutoff.isoformat()))
            return cursor.fetchall()

    def store_alert(self, alert):
        """Store an alert"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO alerts
                (timestamp, room_id, patient_id, alert_type, severity, message)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                alert['timestamp'],
                alert['room_id'],
                alert['patient_id'],
                alert['alert_type'],
                alert['severity'],
                alert['message']
            ))
            conn.commit()

    def get_active_alerts(self):
        """Get unacknowledged alerts"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT * FROM alerts
                WHERE acknowledged = FALSE
                ORDER BY timestamp DESC
            ''')
            return cursor.fetchall()

class AlertEngine:
    def __init__(self, db_manager):
        self.db = db_manager
        self.alert_thresholds = {
            'cough_frequency': 5,  # coughs per hour
            'breathing_rate_low': 8,  # bpm
            'breathing_rate_high': 25,  # bpm
            'hap_risk_score': 0.7  # threshold for HAP risk
        }

    def calculate_hap_risk_score(self, room_data):
        """Calculate Hospital-Acquired Pneumonia risk score"""
        if not room_data:
            return 0.0

        # Simple risk scoring based on cough frequency and breathing rate
        recent_coughs = sum(1 for row in room_data if row[4])  # cough_detected
        avg_breathing_rate = np.mean([row[6] for row in room_data])  # breathing_rate

        # Normalize factors
        cough_factor = min(recent_coughs / 10, 1.0)  # Max at 10 coughs
        breathing_factor = 0.0
        if avg_breathing_rate < self.alert_thresholds['breathing_rate_low']:
            breathing_factor = 0.5
        elif avg_breathing_rate > self.alert_thresholds['breathing_rate_high']:
            breathing_factor = 0.8

        risk_score = (cough_factor * 0.6) + (breathing_factor * 0.4)
        return risk_score

    def check_alerts(self, data):
        """Check if alerts should be triggered"""
        alerts = []

        # Cough frequency alert
        recent_data = self.db.get_recent_data(data['room_id'], hours=1)
        cough_count = sum(1 for row in recent_data if row[4])
        if cough_count >= self.alert_thresholds['cough_frequency']:
            alerts.append({
                'timestamp': datetime.now().isoformat(),
                'room_id': data['room_id'],
                'patient_id': data['patient_id'],
                'alert_type': 'high_cough_frequency',
                'severity': 'medium',
                'message': f'High cough frequency detected: {cough_count} coughs in last hour'
            })

        # Breathing rate alerts
        if data['breathing_rate'] < self.alert_thresholds['breathing_rate_low']:
            alerts.append({
                'timestamp': datetime.now().isoformat(),
                'room_id': data['room_id'],
                'patient_id': data['patient_id'],
                'alert_type': 'low_breathing_rate',
                'severity': 'high',
                'message': f'Low breathing rate: {data["breathing_rate"]:.1f} bpm'
            })
        elif data['breathing_rate'] > self.alert_thresholds['breathing_rate_high']:
            alerts.append({
                'timestamp': datetime.now().isoformat(),
                'room_id': data['room_id'],
                'patient_id': data['patient_id'],
                'alert_type': 'high_breathing_rate',
                'severity': 'high',
                'message': f'High breathing rate: {data["breathing_rate"]:.1f} bpm'
            })

        # HAP risk alert
        hap_risk = self.calculate_hap_risk_score(recent_data)
        if hap_risk >= self.alert_thresholds['hap_risk_score']:
            alerts.append({
                'timestamp': datetime.now().isoformat(),
                'room_id': data['room_id'],
                'patient_id': data['patient_id'],
                'alert_type': 'hap_risk',
                'severity': 'critical',
                'message': f'High HAP risk score: {hap_risk:.2f}'
            })

        return alerts

class HospitalServer:
    def __init__(self):
        self.db = DatabaseManager(DB_PATH)
        self.alert_engine = AlertEngine(self.db)

        # MQTT setup
        self.client = SimpleMQTTClient("hospital_server")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(MQTT_BROKER, MQTT_PORT)

    def on_connect(self, client, userdata, flags, rc):
        print("Connected to MQTT broker")
        client.subscribe("hospital/rooms/+/respiratory")

    def on_message(self, client, userdata, msg):
        """Handle incoming respiratory data"""
        try:
            data = json.loads(msg.payload.decode())
            print(f"📥 Server received data from room {data['room_id']}: cough={data['cough_detected']}, breathing={data['breathing_rate']:.1f}")

            # Store data
            self.db.store_respiratory_data(data)

            # Check for alerts
            alerts = self.alert_engine.check_alerts(data)
            for alert in alerts:
                self.db.store_alert(alert)
                print(f"🚨 Alert generated: {alert['message']}")

                # Publish alert to MQTT for dashboard/mobile
                alert_topic = f"hospital/alerts/{alert['room_id']}"
                self.client.publish(alert_topic, json.dumps(alert))

        except Exception as e:
            print(f"❌ Error processing message: {e}")

    def run(self):
        """Main loop"""
        print("Starting Hospital Server...")
        self.client.subscribe("hospital/rooms/+/respiratory")
        self.client.loop_forever()

if __name__ == "__main__":
    server = HospitalServer()
    server.run()