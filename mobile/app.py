#!/usr/bin/env python3
"""
AI-Powered Ambient Stethoscope - Mobile App Simulator
Simulates mobile app receiving alerts and displaying notifications
"""

import sys
import os
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO_ROOT)
sys.path.insert(0, os.path.join(_REPO_ROOT, "common"))
import json
import time
from datetime import datetime
from common.simple_broker import SimpleMQTTClient

class MobileApp:
    def __init__(self, nurse_id="nurse_001"):
        self.nurse_id = nurse_id

        # MQTT setup
        self.client = SimpleMQTTClient(f"mobile_{self.nurse_id}")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect("localhost", 1883)

    def on_connect(self, client, userdata, flags, rc):
        print(f"📱 Mobile App connected for {self.nurse_id}")
        # Subscribe to all room alerts
        self.client.subscribe("hospital/alerts/+")

    def on_message(self, client, userdata, msg):
        """Handle incoming alerts"""
        try:
            alert = json.loads(msg.payload.decode())
            self.display_notification(alert)
        except Exception as e:
            print(f"❌ Error processing alert: {e}")

    def display_notification(self, alert):
        """Display push notification"""
        timestamp = datetime.fromisoformat(alert['timestamp']).strftime("%H:%M:%S")

        severity_emoji = {
            'critical': '🚨',
            'high': '⚠️',
            'medium': '🔔'
        }.get(alert['severity'], '🔔')

        print(f"""
{severity_emoji} ALERT RECEIVED {severity_emoji}
Time: {timestamp}
Room: {alert['room_id']}
Type: {alert['alert_type'].replace('_', ' ').title()}
Message: {alert['message']}
Patient ID: {alert['patient_id']}
---
""")

    def run(self):
        """Main loop"""
        print(f"Starting Mobile App Simulator for {self.nurse_id}...")
        self.client.loop_forever()

if __name__ == "__main__":
    app = MobileApp()
    app.run()