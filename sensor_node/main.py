#!/usr/bin/env python3
"""
AI-Powered Ambient Stethoscope - Sensor Node Simulator
Simulates microphone array capture, feature extraction, and ML inference
"""

import time
import random
import json
# import paho.mqtt.client as mqtt
from datetime import datetime
import numpy as np
# import librosa  # Simplified for demo
from sklearn.ensemble import RandomForestClassifier
import joblib
import os
import sys
sys.path.append('/workspaces/AI-Powered-Ambient-Stethoscope-for-Hospital-Acquired-Infections/common')
from simple_broker import SimpleMQTTClient

# Configuration
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
ROOM_ID = "312A"
PATIENT_ID = "encrypted_patient_123"

# Audio simulation parameters
SAMPLE_RATE = 16000
WINDOW_SIZE = 1.0  # 1 second windows
COUGH_PROBABILITY = 0.1  # Probability of cough per window
BREATHING_RATE_BASE = 12  # breaths per minute
BREATHING_VARIANCE = 2

class AudioSimulator:
    def __init__(self):
        self.sample_rate = SAMPLE_RATE
        self.window_samples = int(WINDOW_SIZE * SAMPLE_RATE)

    def generate_audio_window(self, has_cough=False, breathing_rate=None):
        """Generate synthetic audio for one window"""
        if breathing_rate is None:
            breathing_rate = BREATHING_RATE_BASE + random.uniform(-BREATHING_VARIANCE, BREATHING_VARIANCE)

        # Generate breathing sounds (simplified)
        breath_duration = 60 / breathing_rate  # seconds per breath
        samples_per_breath = int(breath_duration * self.sample_rate)

        # Create breathing pattern
        t = np.linspace(0, WINDOW_SIZE, self.window_samples)
        breathing_signal = 0.1 * np.sin(2 * np.pi * breathing_rate / 60 * t)  # Low amplitude breathing

        # Add noise
        noise = 0.05 * np.random.randn(self.window_samples)

        # Add cough if present
        if has_cough:
            cough_start = random.randint(0, self.window_samples - int(0.5 * self.sample_rate))
            cough_samples = int(0.5 * self.sample_rate)  # 0.5 second cough
            cough_signal = np.zeros(self.window_samples)
            # Simple cough envelope
            envelope = np.exp(-np.linspace(0, 3, cough_samples))
            cough_wave = 0.8 * envelope * np.random.randn(cough_samples)
            cough_signal[cough_start:cough_start + cough_samples] = cough_wave
            breathing_signal += cough_signal

        return breathing_signal + noise

class FeatureExtractor:
    def __init__(self):
        pass

    def extract_features(self, audio):
        """Extract simplified audio features for ML"""
        # Simplified features without librosa
        # RMS energy
        rms = np.sqrt(np.mean(audio**2))

        # Zero crossing rate
        zcr = np.sum(np.abs(np.diff(np.sign(audio)))) / len(audio)

        # Spectral centroid (simplified)
        fft = np.fft.fft(audio)
        freqs = np.fft.fftfreq(len(audio), 1/SAMPLE_RATE)
        magnitude = np.abs(fft)
        spectral_centroid = np.sum(freqs * magnitude) / np.sum(magnitude)

        # Simple MFCC-like features (first few coefficients)
        # This is a very simplified version
        mfcc_like = []
        for i in range(5):  # 5 coefficients
            coeff = np.mean(audio * np.cos(2 * np.pi * (i+1) * np.arange(len(audio)) / len(audio)))
            mfcc_like.append(coeff)

        features = np.array([
            rms,
            zcr,
            spectral_centroid,
            *mfcc_like,
            np.std(audio),  # Standard deviation
            np.max(audio),  # Peak amplitude
        ])

        return features

class MLClassifier:
    def __init__(self):
        self.model_path = "/workspaces/AI-Powered-Ambient-Stethoscope-for-Hospital-Acquired-Infections/common/cough_classifier.pkl"
        if os.path.exists(self.model_path):
            self.model = joblib.load(self.model_path)
        else:
            # Train a simple model if not exists
            self.train_dummy_model()

    def train_dummy_model(self):
        """Train a dummy classifier for demo"""
        # Generate dummy training data
        np.random.seed(42)
        n_samples = 1000
        n_features = 10  # Our simplified features

        X = np.random.randn(n_samples, n_features)
        y = np.random.choice([0, 1], n_samples, p=[0.8, 0.2])  # Mostly no cough

        self.model = RandomForestClassifier(n_estimators=10, random_state=42)
        self.model.fit(X, y)

        # Save model
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        joblib.dump(self.model, self.model_path)

    def predict_cough(self, features):
        """Predict if cough is present"""
        prediction = self.model.predict([features])[0]
        confidence = max(self.model.predict_proba([features])[0])
        return bool(prediction), confidence

    def estimate_breathing_rate(self, audio):
        """Simple breathing rate estimation"""
        # In real implementation, this would be more sophisticated
        # For demo, return simulated rate
        return BREATHING_RATE_BASE + random.uniform(-BREATHING_VARIANCE, BREATHING_VARIANCE)

class SensorNode:
    def __init__(self):
        self.audio_sim = AudioSimulator()
        self.feature_extractor = FeatureExtractor()
        self.classifier = MLClassifier()

        # MQTT setup
        self.client = SimpleMQTTClient("sensor_node")
        self.client.connect(MQTT_BROKER, MQTT_PORT)

    def process_window(self):
        """Process one audio window"""
        # Simulate cough occurrence
        has_cough = random.random() < COUGH_PROBABILITY

        # Generate audio
        audio = self.audio_sim.generate_audio_window(has_cough=has_cough)

        # Extract features
        features = self.feature_extractor.extract_features(audio)

        # ML prediction
        cough_detected, cough_confidence = self.classifier.predict_cough(features)
        breathing_rate = self.classifier.estimate_breathing_rate(audio)

        # Prepare data
        data = {
            "timestamp": datetime.now().isoformat(),
            "room_id": ROOM_ID,
            "patient_id": PATIENT_ID,
            "cough_detected": cough_detected,
            "cough_confidence": float(cough_confidence),
            "breathing_rate": float(breathing_rate),
            "audio_features": features.tolist()  # For potential further analysis
        }

        return data

    def send_data(self, data):
        """Send data via MQTT"""
        topic = f"hospital/rooms/{ROOM_ID}/respiratory"
        payload = json.dumps(data)
        self.client.publish(topic, payload)
        print(f"Sent data: {data}")

    def run(self):
        """Main loop"""
        print("Starting Sensor Node Simulator...")
        while True:
            data = self.process_window()
            self.send_data(data)
            time.sleep(WINDOW_SIZE)  # Real-time simulation

if __name__ == "__main__":
    node = SensorNode()
    node.run()