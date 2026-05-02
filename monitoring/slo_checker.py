#!/usr/bin/env python3
"""
SLO Checker & Chaos Reporter
Queries Prometheus for SLO breaches (e.g., high error rate or pod downtime).
If a breach is detected, it sends a synthetic Alertmanager webhook to the PostmortemAI service.
"""

import os
import time
import uuid
import datetime
import requests

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8000/alert")

# SLO: Ensure demo-app is up and running. If `up` == 0, SLO is breached.
# Alternatively, check error rate. We'll use a simple `up` query for pod deletion chaos.
PROMETHEUS_QUERY = 'up{app="demo-broken-app"} == 0'

def check_slo():
    print(f"Checking SLO at {PROMETHEUS_URL} with query: {PROMETHEUS_QUERY}")
    try:
        response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": PROMETHEUS_QUERY})
        response.raise_for_status()
        data = response.json()
        
        results = data.get("data", {}).get("result", [])
        if results:
            print(f"🚨 SLO Breach Detected! {len(results)} instances down.")
            return True, results
        else:
            print("✅ SLO is healthy.")
            return False, []
            
    except Exception as e:
        print(f"Error querying Prometheus: {e}")
        # In a real scenario, returning False might suppress monitoring issues,
        # but for this demo we'll just return False to not spam alerts.
        return False, []

def trigger_ai_analysis(breached_instances):
    """
    Simulate an Alertmanager webhook to the FastAPI service.
    We add the 'chaos_experiment=true' label so the AI knows it's a chaos test.
    """
    for instance in breached_instances:
        metric = instance.get("metric", {})
        pod_name = metric.get("pod", "demo-broken-app-unknown")
        namespace = metric.get("namespace", "default")
        
        # Craft Alertmanager payload
        payload = {
            "version": "4",
            "groupKey": "chaos-group",
            "status": "firing",
            "receiver": "postmortem-ai",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "ChaosExperimentSLOBreach",
                        "namespace": namespace,
                        "pod": pod_name,
                        "severity": "CRITICAL",
                        "chaos_experiment": "true"  # Tells the AI Analyzer it's a chaos test
                    },
                    "annotations": {
                        "summary": "Chaos experiment caused an SLO breach",
                        "description": f"Pod {pod_name} became unavailable during the chaos experiment."
                    },
                    "startsAt": datetime.datetime.utcnow().isoformat() + "Z",
                    "endsAt": datetime.datetime.utcnow().isoformat() + "Z",
                }
            ]
        }
        
        print(f"Sending alert to {FASTAPI_URL} for pod {pod_name}...")
        try:
            resp = requests.post(FASTAPI_URL, json=payload)
            resp.raise_for_status()
            print("✅ Successfully triggered AI analysis.")
            print("Response:", resp.json())
        except Exception as e:
            print(f"❌ Failed to trigger AI analysis: {e}")

if __name__ == "__main__":
    is_breached, instances = check_slo()
    if is_breached:
        trigger_ai_analysis(instances)
