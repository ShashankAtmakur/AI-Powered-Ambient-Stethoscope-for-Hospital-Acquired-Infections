#!/usr/bin/env python3
"""
AI-Powered Ambient Stethoscope - EHR Integration Simulator
Simulates integration with Electronic Health Record system
"""

import paho.mqtt.client as mqtt
import json
import sqlite3
from datetime import datetime
import sys
sys.path.append('/workspaces/AI-Powered-Ambient-Stethoscope-for-Hospital-Acquired-Infections/common')
from simple_broker import SimpleMQTTClient

# Configuration
EHR_DB_PATH = "/workspaces/AI-Powered-Ambient-Stethoscope-for-Hospital-Acquired-Infections/ehr/ehr_logs.db"

class EHRIntegration:
    def __init__(self):
        self.init_ehr_db()

        # MQTT setup
        self.client = SimpleMQTTClient("ehr_integration")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect("localhost", 1883)

    def init_ehr_db(self):
        """Initialize EHR database"""
        with sqlite3.connect(EHR_DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS ehr_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    patient_id TEXT,
                    event_type TEXT,
                    details TEXT,
                    hl7_message TEXT
                )
            ''')
            conn.commit()

    def on_connect(self, client, userdata, flags, rc):
        print("🏥 EHR Integration connected")
        self.client.subscribe("hospital/alerts/+")

    def on_message(self, client, userdata, msg):
        """Handle incoming alerts for EHR logging"""
        try:
            alert = json.loads(msg.payload.decode())
            self.log_to_ehr(alert)
        except Exception as e:
            print(f"❌ Error processing EHR alert: {e}")

    def generate_hl7_message(self, alert):
        """Generate simulated HL7 message for EHR"""
        # Simplified HL7-like message
        timestamp = datetime.fromisoformat(alert['timestamp']).strftime("%Y%m%d%H%M%S")

        hl7_message = f"""MSH|^~\\&|AMBSTETH|HOSPITAL|EHR|HOSPITAL|{timestamp}||ORU^R01|{alert['id']}|P|2.5
PID|1||{alert['patient_id']}||Patient^Name||19700101|M|||123 Main St^^Anytown^ST^12345||(555)555-5555|||||
OBR|1||{alert['id']}|RESP^Respiratory Alert|||20240101||||||{timestamp}||||||||||F
OBX|1|ST|ALERT_TYPE||{alert['alert_type']}||||||F
OBX|2|ST|SEVERITY||{alert['severity']}||||||F
OBX|3|ST|MESSAGE||{alert['message']}||||||F
OBX|4|ST|ROOM||{alert['room_id']}||||||F"""

        return hl7_message

    def log_to_ehr(self, alert):
        """Log alert to EHR system"""
        hl7_message = self.generate_hl7_message(alert)

        with sqlite3.connect(EHR_DB_PATH) as conn:
            conn.execute('''
                INSERT INTO ehr_logs
                (timestamp, patient_id, event_type, details, hl7_message)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                alert['timestamp'],
                alert['patient_id'],
                'respiratory_alert',
                json.dumps(alert),
                hl7_message
            ))
            conn.commit()

        print(f"📋 Logged to EHR: {alert['alert_type']} for patient {alert['patient_id']} in room {alert['room_id']}")
        print(f"   HL7 Message generated and stored")

    def run(self):
        """Main loop"""
        print("Starting EHR Integration Simulator...")
        self.client.loop_forever()

if __name__ == "__main__":
    ehr = EHRIntegration()
    ehr.run()