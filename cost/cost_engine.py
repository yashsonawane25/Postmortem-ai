#!/usr/bin/env python3
"""
Cost Engine for PostmortemAI (Phase 3).
Queries OpenCost to calculate total cost, CPU/RAM cost, and efficiency per namespace.
If OpenCost is unavailable (e.g. demo mode), it falls back to simulated data.
"""

import os
import sys
import time
import requests
import random
import logging

# Add service directory to path to import db
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'service')))
from core.db import save_cost_metrics, init_db

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

OPENCOST_URL = os.environ.get("OPENCOST_URL", "http://opencost.opencost.svc.cluster.local:9003")

def fetch_opencost_data():
    """Attempt to fetch real allocation data from OpenCost."""
    url = f"{OPENCOST_URL}/allocation/compute?window=1d&aggregate=namespace"
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("code") == 200 and data.get("data"):
            metrics = []
            allocations = data["data"][0]
            for ns, alloc in allocations.items():
                metrics.append({
                    "namespace": ns,
                    "total_cost": float(alloc.get("totalCost", 0.0)),
                    "cpu_cost": float(alloc.get("cpuCost", 0.0)),
                    "ram_cost": float(alloc.get("ramCost", 0.0)),
                    "efficiency": float(alloc.get("totalEfficiency", 1.0))
                })
            return metrics
    except Exception as e:
        logger.warning(f"Failed to fetch real OpenCost data: {e}")
    return None

def generate_simulated_cost():
    """Generate realistic fake cost metrics for demo purposes."""
    return [
        {
            "namespace": "default",
            "total_cost": round(random.uniform(10.0, 50.0), 2),
            "cpu_cost": round(random.uniform(5.0, 30.0), 2),
            "ram_cost": round(random.uniform(5.0, 20.0), 2),
            "efficiency": round(random.uniform(0.3, 0.9), 2)
        },
        {
            "namespace": "monitoring",
            "total_cost": round(random.uniform(50.0, 150.0), 2),
            "cpu_cost": round(random.uniform(30.0, 100.0), 2),
            "ram_cost": round(random.uniform(20.0, 50.0), 2),
            "efficiency": round(random.uniform(0.6, 0.95), 2)
        },
        {
            "namespace": "opencost",
            "total_cost": round(random.uniform(2.0, 10.0), 2),
            "cpu_cost": round(random.uniform(1.0, 5.0), 2),
            "ram_cost": round(random.uniform(1.0, 5.0), 2),
            "efficiency": round(random.uniform(0.7, 0.99), 2)
        }
    ]

def main():
    logger.info("Initializing Cost Engine...")
    init_db()
    
    while True:
        metrics = fetch_opencost_data()
        if not metrics:
            logger.info("Using simulated cost data for the demo.")
            metrics = generate_simulated_cost()
            
        logger.info(f"Saving cost metrics for {len(metrics)} namespaces.")
        save_cost_metrics(metrics)
        time.sleep(30)

if __name__ == "__main__":
    main()
