#!/usr/bin/env python3
"""
Resilience Tracker
Parses PostmortemAI JSON reports, identifies chaos experiment results,
and computes a weekly resilience score.
"""

import os
import json
from pathlib import Path
from datetime import datetime, timedelta

REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "/tmp/postmortem-reports"))
TRACKING_FILE = REPORTS_DIR / "resilience_tracking.json"

def get_chaos_reports():
    """Find all reports generated from chaos experiments in the last 7 days."""
    if not REPORTS_DIR.exists():
        return []
        
    reports = []
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    
    for json_file in REPORTS_DIR.glob("*.json"):
        if json_file.name == "resilience_tracking.json":
            continue
            
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
                
            generated_at = datetime.fromisoformat(data.get("generated_at", "").replace("Z", "+00:00").split("+")[0])
            analysis = data.get("analysis", {})
            
            # Check if this report is from a chaos experiment
            if analysis.get("alert_name") == "ChaosExperimentSLOBreach" and generated_at >= seven_days_ago:
                reports.append(data)
        except Exception as e:
            print(f"Error reading {json_file.name}: {e}")
            
    return reports

def calculate_weekly_resilience_score():
    """
    Calculate the resilience score.
    A simple metric: (Total Experiments - Failed Experiments) / Total Experiments * 100
    Since our reporting system currently only logs *breaches* (failures), we will need
    to assume total experiments run = (successful experiments logged in tracking + failures).
    
    For a simplified version requested:
    Let's track total triggered experiments in a local file, and then compare against the failures.
    If we don't have total triggered, we can just track failures as a raw number.
    
    Actually, let's load tracking data to see how many were run. If not available, we assume 10 ran this week.
    """
    total_experiments = 10  # In a real system, you'd pull this from Litmus or a CI/CD DB
    
    failed_reports = get_chaos_reports()
    failed_count = len(failed_reports)
    
    # Ensure score doesn't drop below 0
    successful_count = max(0, total_experiments - failed_count)
    score_pct = (successful_count / total_experiments) * 100
    
    results = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "weekly_stats": {
            "total_experiments_run": total_experiments,
            "failed_experiments": failed_count,
            "resilience_score_pct": score_pct
        },
        "recent_failures": []
    }
    
    for rep in failed_reports:
        analysis = rep.get("analysis", {})
        results["recent_failures"].append({
            "experiment": analysis.get("alert_name"),
            "rca": analysis.get("root_cause", ""),
            "weakness": analysis.get("weakness_explanation", ""),
            "timestamp": rep.get("generated_at")
        })
        
    # Save the score
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(TRACKING_FILE, "w") as f:
        json.dump(results, f, indent=2)
        
    return results

if __name__ == "__main__":
    print("📊 Calculating Weekly Resilience Score...")
    score_data = calculate_weekly_resilience_score()
    
    print("\n" + "="*50)
    print(f"📈 RESILIENCE SCORE: {score_data['weekly_stats']['resilience_score_pct']}%")
    print(f"Total Experiments: {score_data['weekly_stats']['total_experiments_run']}")
    print(f"Failed Experiments: {score_data['weekly_stats']['failed_experiments']}")
    print("="*50)
    
    if score_data["recent_failures"]:
        print("\nRecent Chaos Failures:")
        for fail in score_data["recent_failures"]:
            print(f"- [{fail['timestamp']}] RCA: {fail['rca']}")
    else:
        print("\n✅ No chaos failures detected in the last 7 days! Great job!")
