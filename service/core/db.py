import os
import json
import uuid
from datetime import datetime
from sqlalchemy import create_engine, text

# Fallback to local SQLite if DATABASE_URL is not set
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:////tmp/postmortem_ai.db")

# If using Render's Postgres, the URL might start with `postgres://`, which SQLAlchemy doesn't support directly
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite needs specific connect_args to avoid thread issues
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

def get_connection():
    return engine.connect()

def init_db():
    with engine.begin() as conn:
        # SaaS Foundation Tables
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR PRIMARY KEY,
                email VARCHAR
            )
        '''))
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS tenants (
                id VARCHAR PRIMARY KEY,
                user_id VARCHAR
            )
        '''))
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS api_keys (
                key VARCHAR PRIMARY KEY,
                tenant_id VARCHAR
            )
        '''))
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS clusters (
                tenant_id VARCHAR PRIMARY KEY,
                last_seen VARCHAR,
                status VARCHAR
            )
        '''))

        # Table for Chaos Experiments
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS chaos_experiments (
                id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR,
                status VARCHAR,
                triggered_at VARCHAR,
                target_pod VARCHAR
            )
        '''))
        # Table for AI Reports
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS ai_reports (
                incident_id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR,
                alert_name VARCHAR,
                severity VARCHAR,
                report_data TEXT,
                created_at VARCHAR
            )
        '''))
        # Table for Cost Reports
        # For PostgreSQL, AUTOINCREMENT is handled by SERIAL
        autoincrement_sql = "INTEGER PRIMARY KEY AUTOINCREMENT" if DATABASE_URL.startswith("sqlite") else "SERIAL PRIMARY KEY"
        conn.execute(text(f'''
            CREATE TABLE IF NOT EXISTS cost_reports (
                id {autoincrement_sql},
                tenant_id VARCHAR,
                namespace VARCHAR,
                total_cost REAL,
                cpu_cost REAL,
                ram_cost REAL,
                efficiency REAL,
                timestamp VARCHAR
            )
        '''))

def register_chaos_experiment(experiment_id: str, target_pod: str, tenant_id: str):
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO chaos_experiments (id, tenant_id, status, triggered_at, target_pod) VALUES (:id, :tenant_id, :status, :triggered_at, :target_pod)"),
            {"id": experiment_id, "tenant_id": tenant_id, "status": "RUNNING", "triggered_at": datetime.utcnow().isoformat(), "target_pod": target_pod}
        )

def fail_chaos_experiment(tenant_id: str = None):
    with engine.begin() as conn:
        if tenant_id:
            conn.execute(
                text("UPDATE chaos_experiments SET status = 'FAILED' WHERE id = (SELECT id FROM chaos_experiments WHERE tenant_id = :tenant_id ORDER BY triggered_at DESC LIMIT 1)"),
                {"tenant_id": tenant_id}
            )
        else:
            conn.execute(
                text("UPDATE chaos_experiments SET status = 'FAILED' WHERE id = (SELECT id FROM chaos_experiments ORDER BY triggered_at DESC LIMIT 1)")
            )

def update_chaos_status(experiment_id: str, status: str, tenant_id: str):
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE chaos_experiments SET status = :status WHERE id = :id AND tenant_id = :tenant_id"),
            {"status": status, "id": experiment_id, "tenant_id": tenant_id}
        )

def get_chaos_status(tenant_id: str):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM chaos_experiments WHERE tenant_id = :tenant_id ORDER BY triggered_at DESC LIMIT 50"),
            {"tenant_id": tenant_id}
        )
        return [dict(row._mapping) for row in result]

def get_resilience_score(tenant_id: str):
    with engine.connect() as conn:
        total = conn.execute(
            text("SELECT COUNT(*) FROM chaos_experiments WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id}
        ).scalar()
        
        failed = conn.execute(
            text("SELECT COUNT(*) FROM chaos_experiments WHERE status = 'FAILED' AND tenant_id = :tenant_id"),
            {"tenant_id": tenant_id}
        ).scalar()
        
    score = 100
    if total > 0:
        success = total - failed
        score = (success / total) * 100
        
    return {
        "total_experiments": total,
        "failed_experiments": failed,
        "resilience_score": score
    }

def save_ai_report(incident_id: str, alert_name: str, severity: str, report_data: dict, tenant_id: str):
    # SQLite uses REPLACE INTO, PostgreSQL uses INSERT ... ON CONFLICT
    with engine.begin() as conn:
        if DATABASE_URL.startswith("sqlite"):
            query = "INSERT OR REPLACE INTO ai_reports (incident_id, tenant_id, alert_name, severity, report_data, created_at) VALUES (:incident_id, :tenant_id, :alert_name, :severity, :report_data, :created_at)"
        else:
            query = """
            INSERT INTO ai_reports (incident_id, tenant_id, alert_name, severity, report_data, created_at) 
            VALUES (:incident_id, :tenant_id, :alert_name, :severity, :report_data, :created_at)
            ON CONFLICT (incident_id) DO UPDATE SET 
                tenant_id = EXCLUDED.tenant_id, 
                alert_name = EXCLUDED.alert_name, 
                severity = EXCLUDED.severity, 
                report_data = EXCLUDED.report_data, 
                created_at = EXCLUDED.created_at
            """
        conn.execute(
            text(query),
            {
                "incident_id": incident_id, 
                "tenant_id": tenant_id, 
                "alert_name": alert_name, 
                "severity": severity, 
                "report_data": json.dumps(report_data), 
                "created_at": datetime.utcnow().isoformat()
            }
        )

def get_latest_ai_report(tenant_id: str):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM ai_reports WHERE tenant_id = :tenant_id ORDER BY created_at DESC LIMIT 1"),
            {"tenant_id": tenant_id}
        ).fetchone()
        
        if row:
            row_dict = dict(row._mapping)
            return {
                "incident_id": row_dict["incident_id"],
                "tenant_id": row_dict["tenant_id"],
                "alert_name": row_dict["alert_name"],
                "severity": row_dict["severity"],
                "report_data": json.loads(row_dict["report_data"]),
                "created_at": row_dict["created_at"]
            }
        return None

def save_cost_metrics(metrics: list, tenant_id: str):
    with engine.begin() as conn:
        timestamp = datetime.utcnow().isoformat()
        for m in metrics:
            conn.execute(
                text("INSERT INTO cost_reports (tenant_id, namespace, total_cost, cpu_cost, ram_cost, efficiency, timestamp) VALUES (:tenant_id, :namespace, :total_cost, :cpu_cost, :ram_cost, :efficiency, :timestamp)"),
                {
                    "tenant_id": tenant_id, 
                    "namespace": m.get("namespace", "unknown"), 
                    "total_cost": m.get("total_cost", 0.0), 
                    "cpu_cost": m.get("cpu_cost", 0.0), 
                    "ram_cost": m.get("ram_cost", 0.0), 
                    "efficiency": m.get("efficiency", 1.0), 
                    "timestamp": timestamp
                }
            )

def get_latest_cost_insights(tenant_id: str):
    with engine.connect() as conn:
        latest_time = conn.execute(
            text("SELECT timestamp FROM cost_reports WHERE tenant_id = :tenant_id ORDER BY timestamp DESC LIMIT 1"),
            {"tenant_id": tenant_id}
        ).scalar()
        
        if not latest_time:
            return []
            
        result = conn.execute(
            text("SELECT * FROM cost_reports WHERE timestamp = :latest_time AND tenant_id = :tenant_id"),
            {"latest_time": latest_time, "tenant_id": tenant_id}
        )
        return [dict(row._mapping) for row in result]

def generate_api_key(tenant_id: str):
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT key FROM api_keys WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id}
        ).scalar()
        
        if existing:
            return existing
            
        new_key = f"sk_live_{uuid.uuid4().hex}"
        conn.execute(
            text("INSERT INTO api_keys (key, tenant_id) VALUES (:key, :tenant_id)"),
            {"key": new_key, "tenant_id": tenant_id}
        )
        return new_key

def get_api_key_for_tenant(tenant_id: str):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT key FROM api_keys WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id}
        ).scalar()

def get_tenant_for_api_key(api_key: str):
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT tenant_id FROM api_keys WHERE key = :key"),
            {"key": api_key}
        ).scalar()

def upsert_cluster_heartbeat(tenant_id: str):
    with engine.begin() as conn:
        if DATABASE_URL.startswith("sqlite"):
            query = "INSERT OR REPLACE INTO clusters (tenant_id, last_seen, status) VALUES (:tenant_id, :last_seen, :status)"
        else:
            query = """
            INSERT INTO clusters (tenant_id, last_seen, status) 
            VALUES (:tenant_id, :last_seen, :status)
            ON CONFLICT (tenant_id) DO UPDATE SET 
                last_seen = EXCLUDED.last_seen, 
                status = EXCLUDED.status
            """
        conn.execute(
            text(query),
            {"tenant_id": tenant_id, "last_seen": datetime.utcnow().isoformat(), "status": "CONNECTED"}
        )

def get_cluster_status(tenant_id: str):
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM clusters WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id}
        ).fetchone()
        
        if not row:
            return {"connected": False, "last_seen": None}
            
        row_dict = dict(row._mapping)
        last_seen = datetime.fromisoformat(row_dict["last_seen"])
        is_connected = (datetime.utcnow() - last_seen).total_seconds() < 30
        return {
            "connected": is_connected,
            "last_seen": row_dict["last_seen"]
        }
