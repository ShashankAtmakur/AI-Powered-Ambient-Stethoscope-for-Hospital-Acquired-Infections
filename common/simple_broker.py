#!/usr/bin/env python3
"""
Simple MQTT Broker Simulator for Demo
A basic in-memory message broker to avoid external dependencies
"""

import threading
import time
import queue
from collections import defaultdict

# Global shared broker instance
_shared_broker = None
_broker_lock = threading.Lock()

def get_shared_broker():
    """Get the shared broker instance"""
    global _shared_broker
    if _shared_broker is None:
        with _broker_lock:
            if _shared_broker is None:
                _shared_broker = SimpleMQTTBroker()
    return _shared_broker

class SimpleMQTTBroker:
    def __init__(self):
        self.subscriptions = defaultdict(list)  # topic -> list of queues
        self.lock = threading.Lock()

    def subscribe(self, topic_pattern, client_queue):
        """Subscribe to a topic"""
        with self.lock:
            self.subscriptions[topic_pattern].append(client_queue)

    def publish(self, topic, message):
        """Publish message to topic"""
        with self.lock:
            # Simple pattern matching (just prefix for demo)
            for pattern, queues in self.subscriptions.items():
                if topic.startswith(pattern) or pattern == topic:
                    for q in queues:
                        try:
                            q.put((topic, message), timeout=1)
                        except:
                            pass  # Queue full, skip

class SimpleMQTTClient:
    def __init__(self, client_id="client"):
        self.client_id = client_id
        self.message_queue = queue.Queue()
        self.broker = get_shared_broker()  # Use shared broker
        self.connected = False

    def connect(self, broker_host="localhost", broker_port=1883):
        """Simulate connection"""
        self.connected = True
        print(f"{self.client_id}: Connected to broker")

    def subscribe(self, topic):
        """Subscribe to topic"""
        if self.connected:
            self.broker.subscribe(topic, self.message_queue)
            print(f"{self.client_id}: Subscribed to {topic}")

    def publish(self, topic, payload):
        """Publish message"""
        if self.connected:
            self.broker.publish(topic, payload)
            print(f"{self.client_id}: Published to {topic}")

    def loop_forever(self):
        """Keep running (for subscribers)"""
        while self.connected:
            try:
                topic, message = self.message_queue.get(timeout=1)
                if hasattr(self, 'on_message'):
                    self.on_message(None, None, type('Message', (), {'topic': topic, 'payload': message})())
            except queue.Empty:
                continue

    def on_connect(self, client, userdata, flags, rc):
        pass

    def on_message(self, client, userdata, msg):
        pass