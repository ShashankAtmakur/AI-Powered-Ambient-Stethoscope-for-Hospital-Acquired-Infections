#!/usr/bin/env python3
"""
AI-Powered Ambient Stethoscope - Complete System Simulator
Runs all components of the hospital monitoring system
"""

import subprocess
import time
import signal
import sys
import os

def run_component(name, command, cwd=None):
    """Run a component in background"""
    print(f"Starting {name}...")
    if cwd:
        process = subprocess.Popen(command, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    else:
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return process

def main():
    processes = []

    try:
        # Note: Using built-in simple MQTT broker simulator
        print("Using built-in MQTT broker simulator (no external dependencies)")
        print()

        # Start server
        server_cmd = "python3 server/main.py"
        server_process = run_component("Hospital Server", server_cmd)
        processes.append(("Hospital Server", server_process))
        time.sleep(2)  # Wait for server to start

        # Start sensor node
        sensor_cmd = "python3 sensor_node/main.py"
        sensor_process = run_component("Sensor Node", sensor_cmd)
        processes.append(("Sensor Node", sensor_process))
        time.sleep(1)

        # Start dashboard
        dashboard_cmd = "python3 dashboard/app.py"
        dashboard_process = run_component("Dashboard", dashboard_cmd, cwd="dashboard")
        processes.append(("Dashboard", dashboard_process))
        time.sleep(1)

        # Start mobile app
        mobile_cmd = "python3 mobile/app.py"
        mobile_process = run_component("Mobile App", mobile_cmd)
        processes.append(("Mobile App", mobile_process))
        time.sleep(1)

        # Start EHR integration
        ehr_cmd = "python3 ehr/integration.py"
        ehr_process = run_component("EHR Integration", ehr_cmd)
        processes.append(("EHR Integration", ehr_process))

        print("\n" + "="*60)
        print("🎉 AI-Powered Ambient Stethoscope Simulator Running!")
        print("="*60)
        print("📊 Dashboard: http://localhost:5000")
        print("🏥 Server: Processing respiratory data")
        print("📱 Mobile: Receiving alerts")
        print("🏥 EHR: Logging alerts")
        print("🦠 Sensor: Simulating cough detection")
        print("\nPress Ctrl+C to stop all components")
        print("="*60)

        # Wait for interrupt
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down all components...")
        for name, process in processes:
            print(f"Stopping {name}...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        print("All components stopped.")

if __name__ == "__main__":
    main()