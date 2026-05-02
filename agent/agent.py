import os
import time
import json
import random
import requests
import psutil
from datetime import datetime

API_KEY = os.environ.get("API_KEY", "")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "5"))

if not API_KEY:
    print("ERROR: API_KEY environment variable is required.")
    exit(1)

HEADERS = {
    "X-API-KEY": API_KEY,
    "Content-Type": "application/json"
}

def send_heartbeat():
    try:
        url = f"{BACKEND_URL}/agent/heartbeat"
        res = requests.post(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            print("[OK] Heartbeat sent")
        else:
            print(f"[WARN] Heartbeat failed: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"[ERROR] Heartbeat request failed: {e}")

def send_metrics():
    try:
        # Collect system metrics using psutil
        cpu_percent = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        mem_mib = mem.used / (1024 * 1024)
        
        # We'll simulate 'cores' and 'MiB' slightly differently to fit the dashboard's expectations
        cpu_cores = (cpu_percent / 100.0) * psutil.cpu_count()
        
        payload = {
            "metrics": {
                "cpu_cores": round(cpu_cores, 2),
                "memory_mib": round(mem_mib, 2)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        url = f"{BACKEND_URL}/agent/metrics"
        res = requests.post(url, headers=HEADERS, json=payload, timeout=5)
        if res.status_code == 200:
            print("[OK] Metrics pushed")
    except Exception as e:
        print(f"[ERROR] Metrics push failed: {e}")

def send_logs():
    try:
        # Simulate some logs that might include application activities or errors
        current_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        log_types = ["INFO", "INFO", "INFO", "WARN", "DEBUG"]
        
        # If CPU is high, simulate some errors
        if psutil.cpu_percent() > 80:
            log_types.append("ERROR")
            log_types.append("ERROR")
            
        logs = []
        for _ in range(random.randint(1, 5)):
            lvl = random.choice(log_types)
            msg = "System operating normally"
            if lvl == "WARN":
                msg = "Memory usage approaching limits"
            elif lvl == "ERROR":
                msg = "CrashLoopBackOff detected in demo-broken-app pod"
                
            logs.append(f"{current_time} [{lvl}] {msg}")
            
        payload = {
            "logs": logs,
            "timestamp": current_time
        }
        url = f"{BACKEND_URL}/agent/logs"
        res = requests.post(url, headers=HEADERS, json=payload, timeout=5)
        if res.status_code == 200:
            print("[OK] Logs pushed")
    except Exception as e:
        print(f"[ERROR] Logs push failed: {e}")

def main():
    print(f"Starting SRE Agent...")
    print(f"Target Backend: {BACKEND_URL}")
    print(f"Polling Interval: {POLL_INTERVAL}s")
    
    while True:
        send_heartbeat()
        send_metrics()
        send_logs()
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
