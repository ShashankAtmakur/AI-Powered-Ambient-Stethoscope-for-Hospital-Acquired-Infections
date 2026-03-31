#!/usr/bin/env python3
"""
Simple MQTT Broker Simulator for Demo
A basic in-memory message broker to avoid external dependencies.
Supports MQTT wildcard patterns: + (single level) and # (multi level).
"""

import threading
import time
import queue
from collections import defaultdict
import re

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


def _topic_matches(pattern: str, topic: str) -> bool:
    """
    Check whether an MQTT topic matches a subscription pattern.

    Supports:
      - ``+`` single-level wildcard (matches exactly one level)
      - ``#`` multi-level wildcard (matches zero or more levels, must be last)
      - Exact match
    """
    if pattern == topic:
        return True
    # Convert MQTT pattern to a regex
    # Escape everything except our wildcards
    regex = re.escape(pattern).replace(r"\+", "[^/]+").replace(r"\#", ".+")
    regex = "^" + regex + "$"
    return re.match(regex, topic) is not None


class SimpleMQTTBroker:
    def __init__(self):
        self.subscriptions = defaultdict(list)  # topic_pattern -> list of queues
        self.lock = threading.Lock()

    def subscribe(self, topic_pattern, client_queue):
        """Subscribe to a topic"""
        with self.lock:
            self.subscriptions[topic_pattern].append(client_queue)

    def publish(self, topic, message):
        """Publish message to all matching subscriptions"""
        with self.lock:
            for pattern, queues in self.subscriptions.items():
                if _topic_matches(pattern, topic):
                    for q in queues:
                        try:
                            q.put((topic, message), timeout=1)
                        except Exception:
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

    def loop_forever(self):
        """Keep running (for subscribers)"""
        while self.connected:
            try:
                topic, message = self.message_queue.get(timeout=1)
                if hasattr(self, 'on_message'):
                    self.on_message(
                        None, None,
                        type('Message', (), {'topic': topic, 'payload': message})()
                    )
            except queue.Empty:
                continue

    def on_connect(self, client, userdata, flags, rc):
        pass

    def on_message(self, client, userdata, msg):
        pass
