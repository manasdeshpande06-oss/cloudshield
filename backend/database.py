"""
CloudShield FairGuard — SQLite database layer.

Uses aiosqlite for async access. Schema creation and seed data are
idempotent: restarting the backend never duplicates rows.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import aiosqlite

DB_PATH = os.environ.get("FAIRGUARD_DB", str(Path(__file__).parent / "fairguard.db"))

# Demo mode flag – when true the backend marks generated data as simulated.
DEMO_MODE = os.getenv("FAIRGUARD_DEMO", "true").lower() in ("1", "true", "yes")

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS companies (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    slug        TEXT NOT NULL UNIQUE,
    api_key     TEXT NOT NULL UNIQUE,
    registered_at TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS tenants (
    id           TEXT PRIMARY KEY,
    company_id   TEXT NOT NULL REFERENCES companies(id),
    name         TEXT NOT NULL,
    workload_type TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'healthy',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tenant_quotas (
    tenant_id              TEXT PRIMARY KEY REFERENCES tenants(id),
    requests_per_minute    INTEGER NOT NULL DEFAULT 500,
    max_concurrency        INTEGER NOT NULL DEFAULT 25,
    queue_limit            INTEGER NOT NULL DEFAULT 100,
    resource_budget_cpu    REAL    NOT NULL DEFAULT 25.0,
    resource_budget_memory REAL    NOT NULL DEFAULT 25.0,
    window_seconds         INTEGER NOT NULL DEFAULT 60,
    updated_at             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fairness_contracts (
    tenant_id         TEXT PRIMARY KEY REFERENCES tenants(id),
    min_cpu_pct       REAL NOT NULL DEFAULT 5.0,
    max_cpu_pct       REAL NOT NULL DEFAULT 40.0,
    priority          INTEGER NOT NULL DEFAULT 5,
    min_rpm           INTEGER NOT NULL DEFAULT 100,
    max_rpm           INTEGER NOT NULL DEFAULT 1000,
    borrow_allowed    INTEGER NOT NULL DEFAULT 1,
    borrow_cap_pct    REAL NOT NULL DEFAULT 10.0,
    notes             TEXT DEFAULT '',
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'active',
    violation_count   INTEGER NOT NULL DEFAULT 0,
    last_violation_at TEXT
);


CREATE TABLE IF NOT EXISTS request_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id   TEXT NOT NULL REFERENCES tenants(id),
    timestamp   TEXT NOT NULL,
    status      TEXT NOT NULL CHECK(status IN ('accepted','rejected')),
    latency_ms  REAL,
    reason      TEXT,
    is_simulated INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_req_tenant_ts ON request_events(tenant_id, timestamp);

CREATE TABLE IF NOT EXISTS jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id    TEXT NOT NULL REFERENCES tenants(id),
    job_type     TEXT NOT NULL DEFAULT 'generic',
    status       TEXT NOT NULL DEFAULT 'queued'
                 CHECK(status IN ('queued','running','completed','failed','cancelled','deferred')),
    priority     INTEGER NOT NULL DEFAULT 5,
    created_at   TEXT NOT NULL,
    started_at   TEXT,
    completed_at TEXT,
    duration_ms  REAL,
    queue_wait_ms REAL,
    worker_id    INTEGER,
    is_simulated INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON jobs(tenant_id, status);

CREATE TABLE IF NOT EXISTS scheduling_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          INTEGER NOT NULL REFERENCES jobs(id),
    tenant_id       TEXT NOT NULL REFERENCES tenants(id),
    company_id      TEXT NOT NULL,
    event           TEXT NOT NULL,
    scheduling_turn INTEGER,
    queue_wait_ms   REAL,
    execution_ms    REAL,
    worker_id       INTEGER,
    result          TEXT,
    decision_reason TEXT,
    timestamp       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sched_tenant ON scheduling_history(tenant_id, timestamp);

CREATE TABLE IF NOT EXISTS resource_measurements (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id         TEXT REFERENCES tenants(id),
    timestamp         TEXT NOT NULL,
    cpu_percent       REAL,
    memory_percent    REAL,
    queue_depth       INTEGER,
    queue_wait_ms     REAL,
    active_jobs       INTEGER,
    scope             TEXT NOT NULL DEFAULT 'machine',
    is_simulated      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_res_ts ON resource_measurements(timestamp);
CREATE INDEX IF NOT EXISTS idx_res_tenant_ts ON resource_measurements(tenant_id, timestamp);

CREATE TABLE IF NOT EXISTS security_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id   TEXT REFERENCES tenants(id),
    timestamp   TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    severity    TEXT NOT NULL DEFAULT 'info',
    description TEXT,
    is_simulated INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_sec_tenant ON security_events(tenant_id, timestamp);

CREATE TABLE IF NOT EXISTS incidents (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id         TEXT NOT NULL REFERENCES tenants(id),
    title             TEXT NOT NULL,
    description       TEXT,
    severity          TEXT NOT NULL DEFAULT 'medium',
    status            TEXT NOT NULL DEFAULT 'open',
    detected_at       TEXT NOT NULL,
    resolved_at       TEXT,
    evidence          TEXT,
    affected_tenants  TEXT,
    detection_rules   TEXT,
    baseline_metrics  TEXT,
    observed_metrics  TEXT,
    is_simulated      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS protection_actions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id    INTEGER REFERENCES incidents(id),
    tenant_id      TEXT NOT NULL REFERENCES tenants(id),
    action_type    TEXT NOT NULL,
    parameters     TEXT,
    applied_at     TEXT,
    rolled_back_at TEXT,
    expires_at     TEXT,
    result_metrics TEXT,
    outcome        TEXT,
    status         TEXT NOT NULL DEFAULT 'pending'
                   CHECK(status IN ('pending','applied','rolled_back','failed','expired'))
);

CREATE TABLE IF NOT EXISTS experiments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id       TEXT NOT NULL REFERENCES tenants(id),
    name            TEXT NOT NULL,
    scenario        TEXT,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending','running','completed','failed')),
    config          TEXT,
    started_at      TEXT,
    completed_at    TEXT,
    before_metrics  TEXT,
    after_metrics   TEXT,
    outcome         TEXT,
    is_simulated    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS controller_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    level       TEXT NOT NULL DEFAULT 'info',
    event       TEXT NOT NULL,
    tenant_id   TEXT REFERENCES tenants(id),
    detail      TEXT
);

CREATE TABLE IF NOT EXISTS api_request_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id    TEXT NOT NULL,
    tenant_id     TEXT,
    company_id    TEXT,
    endpoint      TEXT NOT NULL,
    method        TEXT NOT NULL,
    status_code   INTEGER NOT NULL,
    duration_ms   REAL NOT NULL,
    throttled     INTEGER NOT NULL DEFAULT 0,
    policy_applied TEXT,
    timestamp     TEXT NOT NULL,
    is_simulated  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_api_req_ts ON api_request_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_api_req_tenant ON api_request_logs(tenant_id, timestamp);

CREATE TABLE IF NOT EXISTS infrastructure_metrics (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id     TEXT,
    source        TEXT NOT NULL,
    cpu_percent   REAL,
    memory_percent REAL,
    disk_percent  REAL,
    timestamp     TEXT NOT NULL,
    is_live       INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_infra_ts ON infrastructure_metrics(timestamp);

CREATE TABLE IF NOT EXISTS audit_logs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    actor         TEXT NOT NULL,
    action        TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id   TEXT,
    details       TEXT,
    timestamp     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_logs(timestamp);

CREATE TABLE IF NOT EXISTS capacity_borrowing_records (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    source_tenant_id     TEXT,
    borrowing_tenant_id  TEXT NOT NULL REFERENCES tenants(id),
    amount_borrowed      REAL NOT NULL,
    time_borrowed        TEXT NOT NULL,
    reason               TEXT NOT NULL,
    amount_reclaimed     REAL DEFAULT 0.0,
    time_reclaimed       TEXT,
    resulting_allocation REAL NOT NULL,
    affected_tenant_id   TEXT,
    policy_rule          TEXT NOT NULL DEFAULT 'adaptive_fairness'
);
CREATE INDEX IF NOT EXISTS idx_cbr_ts ON capacity_borrowing_records(time_borrowed);

CREATE TABLE IF NOT EXISTS policy_enforcement_records (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id            TEXT NOT NULL REFERENCES tenants(id),
    triggering_condition TEXT NOT NULL,
    measured_evidence    TEXT NOT NULL,
    policy_rule          TEXT NOT NULL,
    action_selected      TEXT NOT NULL,
    action_result        TEXT NOT NULL,
    timestamp            TEXT NOT NULL,
    resulting_measurements TEXT
);
CREATE INDEX IF NOT EXISTS idx_per_ts ON policy_enforcement_records(timestamp);

CREATE TABLE IF NOT EXISTS fairness_lab_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT UNIQUE NOT NULL,
    scenario_id     TEXT NOT NULL,
    scenario_name   TEXT NOT NULL,
    burst_factor    REAL NOT NULL,
    total_workers   INTEGER NOT NULL,
    quota_per_tenant INTEGER NOT NULL,
    seed            INTEGER NOT NULL,
    recommended_policy TEXT NOT NULL,
    result_json     TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_flab_ts ON fairness_lab_runs(created_at);
"""


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

async def get_db() -> aiosqlite.Connection:
    """Return a new async database connection with row_factory enabled."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db() -> None:
    """Create tables (idempotent) and seed demo data."""
    db = await get_db()
    try:
        await db.executescript(SCHEMA_SQL)
        await _migrate(db)
        await _seed(db)
        await _ensure_all_tenants_and_contracts(db)
        await db.commit()
    finally:
        await db.close()


async def _ensure_all_tenants_and_contracts(db: aiosqlite.Connection) -> None:
    """
    Ensure all standard companies (including Shop A, Game B, Food C),
    tenants, quotas, and fairness contracts are populated even if the DB
    was previously initialized.
    """
    now = datetime.now(timezone.utc)
    reg_date = (now - timedelta(days=270)).isoformat()
    now_iso = now.isoformat()

    # 1. Ensure all companies exist
    for c in _COMPANIES:
        cur_c = await db.execute("SELECT id FROM companies WHERE slug = ?", (c["slug"],))
        existing_c = await cur_c.fetchone()
        if not existing_c:
            cur_max = await db.execute("SELECT MAX(CAST(SUBSTR(id, 6) AS INTEGER)) FROM companies WHERE id LIKE 'COMP-%'")
            (max_id,) = await cur_max.fetchone()
            next_num = (max_id or 10) + 1
            cid = f"COMP-{next_num:03d}"
            key = f"fg_demo_{c['slug']}"
            await db.execute(
                """INSERT INTO companies (id, name, slug, api_key, registered_at, status)
                   VALUES (?, ?, ?, ?, ?, 'active')""",
                (cid, c["name"], c["slug"], key, reg_date),
            )

    # Build slug -> id mapping
    cursor = await db.execute("SELECT id, slug FROM companies")
    slug_to_id = {row["slug"]: row["id"] for row in await cursor.fetchall()}

    # 2. Ensure all tenants exist with quotas
    for t in _TENANTS:
        cid = slug_to_id.get(t["company"], "COMP-001")
        await db.execute(
            """INSERT INTO tenants (id, company_id, name, workload_type, status, created_at)
               VALUES (?, ?, ?, ?, 'healthy', ?)
               ON CONFLICT(id) DO UPDATE SET company_id = excluded.company_id, name = excluded.name""",
            (t["id"], cid, t["name"], t["workload"], reg_date),
        )
        await db.execute(
            """INSERT OR IGNORE INTO tenant_quotas
               (tenant_id, requests_per_minute, max_concurrency, queue_limit,
                resource_budget_cpu, resource_budget_memory, window_seconds, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 60, ?)""",
            (t["id"], t["quota"], t["concurrency"], t["queue_limit"],
             t["cpu_budget"], t["mem_budget"], now_iso),
        )

    # 3. Ensure ALL tenants have active fairness contracts
    cursor = await db.execute("SELECT id, name FROM tenants")
    tenants = await cursor.fetchall()

    priority_map = {
        "shop_a": (4.0, 35.0, 8, 200, 800, 15.0),
        "game_b": (4.0, 40.0, 5, 150, 1000, 20.0),
        "food_c": (3.0, 30.0, 6, 120, 600, 10.0),
        "tn_northstar_01": (6.0, 35.0, 7, 200, 800, 10.0),
        "tn_lattice_02": (6.0, 30.0, 8, 300, 1200, 15.0),
        "tn_meridian_04": (6.0, 40.0, 9, 200, 1000, 10.0),
        "tn_pioneer_07": (4.0, 25.0, 5, 100, 500, 10.0),
        "tn_cedar_11": (4.0, 30.0, 6, 150, 600, 10.0),
    }

    for t in tenants:
        tid = t["id"]
        tname = t["name"]
        min_cpu, max_cpu, prio, min_rpm, max_rpm, b_cap = priority_map.get(
            tid, (1.5, 30.0, 5, 100, 600, 10.0)
        )
        await db.execute(
            """INSERT INTO fairness_contracts
               (tenant_id, min_cpu_pct, max_cpu_pct, priority, min_rpm, max_rpm,
                borrow_allowed, borrow_cap_pct, notes, created_at, updated_at, status)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, 'active')
               ON CONFLICT(tenant_id) DO UPDATE SET
                 min_cpu_pct = excluded.min_cpu_pct,
                 max_cpu_pct = excluded.max_cpu_pct,
                 priority = excluded.priority,
                 min_rpm = excluded.min_rpm,
                 max_rpm = excluded.max_rpm,
                 borrow_cap_pct = excluded.borrow_cap_pct""",
            (tid, min_cpu, max_cpu, prio, min_rpm, max_rpm, b_cap,
             f"Contract for {tname}", now_iso, now_iso),
        )

    # 4. Ensure Shop A, Game B, Food C have baseline requests
    for tid, base_lat, count in [("shop_a", 32.0, 48), ("game_b", 30.0, 54), ("food_c", 28.0, 36)]:
        cur_req = await db.execute("SELECT COUNT(*) FROM request_events WHERE tenant_id = ?", (tid,))
        (cnt,) = await cur_req.fetchone()
        if cnt == 0:
            for j in range(count):
                ts = (now - timedelta(minutes=count - j)).isoformat()
                await db.execute(
                    "INSERT INTO request_events (tenant_id, timestamp, status, latency_ms, is_simulated) VALUES (?,?,?,?,1)",
                    (tid, ts, "accepted", round(base_lat + (j % 5) - 2, 1)),
                )



async def _migrate(db: aiosqlite.Connection) -> None:
    """Add new columns to existing tables if they are missing (safe migration)."""
    migrations = [
        ("tenant_quotas", "queue_limit", "INTEGER NOT NULL DEFAULT 100"),
        ("tenant_quotas", "resource_budget_cpu", "REAL NOT NULL DEFAULT 25.0"),
        ("tenant_quotas", "resource_budget_memory", "REAL NOT NULL DEFAULT 25.0"),
        ("jobs", "job_type", "TEXT NOT NULL DEFAULT 'generic'"),
        ("jobs", "priority", "INTEGER NOT NULL DEFAULT 5"),
        ("jobs", "queue_wait_ms", "REAL"),
        ("jobs", "is_simulated", "INTEGER NOT NULL DEFAULT 0"),
        ("scheduling_history", "company_id", "TEXT NOT NULL DEFAULT ''"),
        ("scheduling_history", "scheduling_turn", "INTEGER"),
        ("scheduling_history", "queue_wait_ms", "REAL"),
        ("scheduling_history", "execution_ms", "REAL"),
        ("scheduling_history", "worker_id", "INTEGER"),
        ("scheduling_history", "result", "TEXT"),
        ("scheduling_history", "decision_reason", "TEXT"),
        ("resource_measurements", "queue_wait_ms", "REAL"),
        ("resource_measurements", "active_jobs", "INTEGER"),
        ("resource_measurements", "scope", "TEXT NOT NULL DEFAULT 'machine'"),
        ("incidents", "affected_tenants", "TEXT"),
        ("incidents", "detection_rules", "TEXT"),
        ("incidents", "baseline_metrics", "TEXT"),
        ("incidents", "observed_metrics", "TEXT"),
        ("protection_actions", "expires_at", "TEXT"),
        ("protection_actions", "result_metrics", "TEXT"),
        ("protection_actions", "outcome", "TEXT"),
        ("experiments", "scenario", "TEXT"),
        ("experiments", "outcome", "TEXT"),
    ]
    for table, col, col_def in migrations:
        try:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
        except Exception:
            pass  # Column already exists

    await db.execute("""
        CREATE TABLE IF NOT EXISTS capacity_borrowing_records (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            source_tenant_id     TEXT,
            borrowing_tenant_id  TEXT NOT NULL REFERENCES tenants(id),
            amount_borrowed      REAL NOT NULL,
            time_borrowed        TEXT NOT NULL,
            reason               TEXT NOT NULL,
            amount_reclaimed     REAL DEFAULT 0.0,
            time_reclaimed       TEXT,
            resulting_allocation REAL NOT NULL,
            affected_tenant_id   TEXT,
            policy_rule          TEXT NOT NULL DEFAULT 'adaptive_fairness'
        )
    """)
    await db.execute("""
        CREATE TABLE IF NOT EXISTS policy_enforcement_records (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id            TEXT NOT NULL REFERENCES tenants(id),
            triggering_condition TEXT NOT NULL,
            measured_evidence    TEXT NOT NULL,
            policy_rule          TEXT NOT NULL,
            action_selected      TEXT NOT NULL,
            action_result        TEXT NOT NULL,
            timestamp            TEXT NOT NULL,
            resulting_measurements TEXT
        )
    """)


# ---------------------------------------------------------------------------
# Deterministic API key helper
# ---------------------------------------------------------------------------

def _make_api_key(company_slug: str) -> str:
    h = hashlib.sha256(f"fairguard-demo-{company_slug}".encode()).hexdigest()[:16]
    return f"fg_demo_{h}"


PLATFORM_ADMIN_KEY = "fg_admin_platform_demo_key"


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

_COMPANIES: list[dict[str, Any]] = [
    {"name": "Northstar Analytics", "slug": "northstar"},
    {"name": "Meridian Health",     "slug": "meridian"},
    {"name": "Pioneer Logistics",   "slug": "pioneer"},
    {"name": "Lattice Finance",     "slug": "lattice"},
    {"name": "Cedar Commerce",      "slug": "cedar"},
    {"name": "Apex Technologies",   "slug": "apex"},
    {"name": "Summit Education",    "slug": "summit"},
    {"name": "Drift Media",         "slug": "drift"},
    {"name": "Cobalt Security",     "slug": "cobalt"},
    {"name": "Ember AI",            "slug": "ember"},
    # Benchmark / Workload Simulation Companies
    {"name": "Shop A Commerce",     "slug": "shop_a"},
    {"name": "Game B Interactive",  "slug": "game_b"},
    {"name": "Food C Delivery",     "slug": "food_c"},
]

_TENANTS: list[dict[str, Any]] = [
    # Northstar Analytics — 3 tenants
    {"id": "tn_northstar_01", "company": "northstar", "name": "Northstar Prod",       "workload": "CPU-intensive",        "quota": 1000, "concurrency": 25, "queue_limit": 200, "cpu_budget": 40.0, "mem_budget": 30.0},
    {"id": "tn_northstar_02", "company": "northstar", "name": "Northstar Staging",    "workload": "CPU-intensive",        "quota": 400,  "concurrency": 10, "queue_limit": 80,  "cpu_budget": 20.0, "mem_budget": 15.0},
    {"id": "tn_northstar_03", "company": "northstar", "name": "Northstar Dev",        "workload": "Batch jobs",           "quota": 200,  "concurrency": 5,  "queue_limit": 50,  "cpu_budget": 10.0, "mem_budget": 10.0},
    # Meridian Health — 2 tenants
    {"id": "tn_meridian_04",  "company": "meridian",  "name": "Meridian API",         "workload": "API / light",          "quota": 500,  "concurrency": 30, "queue_limit": 150, "cpu_budget": 15.0, "mem_budget": 20.0},
    {"id": "tn_meridian_05",  "company": "meridian",  "name": "Meridian Analytics",   "workload": "Mixed workload",       "quota": 300,  "concurrency": 15, "queue_limit": 100, "cpu_budget": 20.0, "mem_budget": 25.0},
    # Pioneer Logistics — 2 tenants
    {"id": "tn_pioneer_07",   "company": "pioneer",   "name": "Pioneer Batch",        "workload": "Batch jobs",           "quota": 750,  "concurrency": 20, "queue_limit": 200, "cpu_budget": 25.0, "mem_budget": 20.0},
    {"id": "tn_pioneer_08",   "company": "pioneer",   "name": "Pioneer Realtime",     "workload": "API / light",          "quota": 400,  "concurrency": 25, "queue_limit": 100, "cpu_budget": 10.0, "mem_budget": 15.0},
    # Lattice Finance — 3 tenants
    {"id": "tn_lattice_02",   "company": "lattice",   "name": "Lattice Trading",      "workload": "API / light",          "quota": 600,  "concurrency": 30, "queue_limit": 150, "cpu_budget": 15.0, "mem_budget": 20.0},
    {"id": "tn_lattice_09",   "company": "lattice",   "name": "Lattice Risk",         "workload": "CPU-intensive",        "quota": 400,  "concurrency": 15, "queue_limit": 100, "cpu_budget": 30.0, "mem_budget": 20.0},
    {"id": "tn_lattice_10",   "company": "lattice",   "name": "Lattice Reports",      "workload": "Batch jobs",           "quota": 250,  "concurrency": 10, "queue_limit": 80,  "cpu_budget": 15.0, "mem_budget": 15.0},
    # Cedar Commerce — 2 tenants
    {"id": "tn_cedar_11",     "company": "cedar",     "name": "Cedar Storefront",     "workload": "Mixed workload",       "quota": 500,  "concurrency": 25, "queue_limit": 120, "cpu_budget": 20.0, "mem_budget": 20.0},
    {"id": "tn_cedar_12",     "company": "cedar",     "name": "Cedar Warehouse",      "workload": "Batch jobs",           "quota": 300,  "concurrency": 15, "queue_limit": 100, "cpu_budget": 15.0, "mem_budget": 15.0},
    # Apex Technologies — 3 tenants
    {"id": "tn_apex_13",      "company": "apex",      "name": "Apex GPU Cluster",     "workload": "GPU compute",          "quota": 200,  "concurrency": 8,  "queue_limit": 40,  "cpu_budget": 50.0, "mem_budget": 40.0},
    {"id": "tn_apex_14",      "company": "apex",      "name": "Apex API Gateway",     "workload": "API / light",          "quota": 800,  "concurrency": 40, "queue_limit": 200, "cpu_budget": 10.0, "mem_budget": 15.0},
    {"id": "tn_apex_15",      "company": "apex",      "name": "Apex ML Pipeline",     "workload": "CPU-intensive",        "quota": 350,  "concurrency": 12, "queue_limit": 80,  "cpu_budget": 35.0, "mem_budget": 30.0},
    # Summit Education — 2 tenants
    {"id": "tn_summit_16",    "company": "summit",    "name": "Summit LMS",           "workload": "API / light",          "quota": 600,  "concurrency": 30, "queue_limit": 150, "cpu_budget": 10.0, "mem_budget": 15.0},
    {"id": "tn_summit_17",    "company": "summit",    "name": "Summit Grading",       "workload": "Batch jobs",           "quota": 250,  "concurrency": 10, "queue_limit": 80,  "cpu_budget": 15.0, "mem_budget": 10.0},
    # Drift Media — 3 tenants
    {"id": "tn_drift_18",     "company": "drift",     "name": "Drift Streaming",      "workload": "Streaming",            "quota": 1000, "concurrency": 50, "queue_limit": 300, "cpu_budget": 20.0, "mem_budget": 30.0},
    {"id": "tn_drift_19",     "company": "drift",     "name": "Drift Encoding",       "workload": "CPU-intensive",        "quota": 300,  "concurrency": 10, "queue_limit": 60,  "cpu_budget": 40.0, "mem_budget": 25.0},
    {"id": "tn_drift_20",     "company": "drift",     "name": "Drift CDN Origin",     "workload": "API / light",          "quota": 500,  "concurrency": 25, "queue_limit": 120, "cpu_budget": 10.0, "mem_budget": 15.0},
    # Cobalt Security — 2 tenants
    {"id": "tn_cobalt_21",    "company": "cobalt",    "name": "Cobalt SIEM",          "workload": "Real-time analytics",  "quota": 700,  "concurrency": 35, "queue_limit": 200, "cpu_budget": 20.0, "mem_budget": 25.0},
    {"id": "tn_cobalt_22",    "company": "cobalt",    "name": "Cobalt Threat Intel",  "workload": "Batch jobs",           "quota": 300,  "concurrency": 12, "queue_limit": 80,  "cpu_budget": 15.0, "mem_budget": 15.0},
    # Ember AI — 3 tenants
    {"id": "tn_ember_23",     "company": "ember",     "name": "Ember Inference",      "workload": "ML inference",         "quota": 500,  "concurrency": 20, "queue_limit": 100, "cpu_budget": 30.0, "mem_budget": 35.0},
    {"id": "tn_ember_24",     "company": "ember",     "name": "Ember Training",       "workload": "GPU compute",          "quota": 150,  "concurrency": 5,  "queue_limit": 30,  "cpu_budget": 60.0, "mem_budget": 50.0},
    {"id": "tn_ember_25",     "company": "ember",     "name": "Ember API",            "workload": "API / light",          "quota": 600,  "concurrency": 30, "queue_limit": 150, "cpu_budget": 10.0, "mem_budget": 15.0},
    # Benchmark / Workload Simulation Tenants
    {"id": "shop_a", "company": "shop_a", "name": "Shop A Storefront", "workload": "e-commerce", "quota": 600, "concurrency": 25, "queue_limit": 150, "cpu_budget": 25.0, "mem_budget": 20.0},
    {"id": "game_b", "company": "game_b", "name": "Game B Live Server", "workload": "gaming", "quota": 500, "concurrency": 25, "queue_limit": 150, "cpu_budget": 25.0, "mem_budget": 20.0},
    {"id": "food_c", "company": "food_c", "name": "Food C Dispatch", "workload": "food-delivery", "quota": 450, "concurrency": 20, "queue_limit": 120, "cpu_budget": 20.0, "mem_budget": 15.0},
]


async def _seed(db: aiosqlite.Connection) -> None:
    """Insert seed data only if the companies table is empty (idempotent)."""
    cursor = await db.execute("SELECT COUNT(*) FROM companies")
    (count,) = await cursor.fetchone()  # type: ignore[misc]
    if count > 0:
        return  # already seeded

    now = datetime.now(timezone.utc)
    reg_date = (now - timedelta(days=270)).isoformat()

    # -- Companies --
    for idx, c in enumerate(_COMPANIES, 1):
        cid = f"COMP-{idx:03d}"
        await db.execute(
            "INSERT INTO companies (id, name, slug, api_key, registered_at, status) VALUES (?,?,?,?,?,?)",
            (cid, c["name"], c["slug"], _make_api_key(c["slug"]), reg_date, "active"),
        )

    # Build slug → id mapping
    slug_to_id: dict[str, str] = {}
    cursor = await db.execute("SELECT id, slug FROM companies")
    for row in await cursor.fetchall():
        slug_to_id[row["slug"]] = row["id"]

    # -- Tenants + quotas --
    for t in _TENANTS:
        company_id = slug_to_id[t["company"]]
        await db.execute(
            "INSERT INTO tenants (id, company_id, name, workload_type, status, created_at) VALUES (?,?,?,?,?,?)",
            (t["id"], company_id, t["name"], t["workload"], "healthy", reg_date),
        )
        await db.execute(
            """INSERT INTO tenant_quotas
               (tenant_id, requests_per_minute, max_concurrency, queue_limit,
                resource_budget_cpu, resource_budget_memory, window_seconds, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (t["id"], t["quota"], t["concurrency"], t["queue_limit"],
             t["cpu_budget"], t["mem_budget"], 60, now.isoformat()),
        )

    # -- Demo incident (Northstar noisy-neighbor) --
    await db.execute(
        """INSERT INTO incidents
           (tenant_id, title, description, severity, status, detected_at,
            evidence, affected_tenants, detection_rules, baseline_metrics, observed_metrics, is_simulated)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "tn_northstar_01",
            "Northstar Analytics may be impacting shared workers",
            "CPU pressure and queue wait increased while 8 CPU-intensive jobs were active.",
            "high", "open",
            (now - timedelta(minutes=14)).isoformat(),
            json.dumps({
                "cpu_percent": 78,
                "p95_latency_increase_ms": 42,
                "queue_depth_increase": 39,
                "active_jobs": 8,
                "evidence_strength": "strong signal, not confirmed causation",
            }),
            json.dumps([
                {"tenant_id": "tn_meridian_04", "company": "Meridian Health",
                 "baseline_p95_ms": 42, "observed_p95_ms": 84, "queue_wait_increase_ms": 320},
                {"tenant_id": "tn_pioneer_08", "company": "Pioneer Logistics",
                 "baseline_p95_ms": 38, "observed_p95_ms": 71, "queue_wait_increase_ms": 210},
            ]),
            json.dumps([
                "cpu_sustained_above_threshold",
                "queue_wait_increased_3_windows",
                "latency_degraded_other_tenants",
                "cpu_intensive_workload_active",
            ]),
            json.dumps({"cpu_percent": 42, "p95_latency_ms": 42, "queue_depth": 18, "queue_wait_ms": 120}),
            json.dumps({"cpu_percent": 78, "p95_latency_ms": 84, "queue_depth": 63, "queue_wait_ms": 440}),
            1,
        ),
    )

    # -- Demo security events --
    _sec_events = [
        ("tn_northstar_01", "concurrency_limit_reduced", "warning", "Concurrency limit reduced for Northstar Analytics", 2),
        ("tn_meridian_04",  "quota_policy_updated",      "info",    "Quota policy updated for Meridian Health", 18),
        ("tn_northstar_01", "fair_scheduler_enabled",    "info",    "Fair scheduler enabled platform-wide", 42),
    ]
    for tid, etype, sev, desc, mins_ago in _sec_events:
        await db.execute(
            "INSERT INTO security_events (tenant_id, timestamp, event_type, severity, description, is_simulated) VALUES (?,?,?,?,?,?)",
            (tid, (now - timedelta(minutes=mins_ago)).isoformat(), etype, sev, desc, 1),
        )

    # -- Demo protection action --
    await db.execute(
        """INSERT INTO protection_actions
           (incident_id, tenant_id, action_type, parameters, applied_at, status, outcome)
           VALUES (?,?,?,?,?,?,?)""",
        (
            1, "tn_northstar_01", "concurrency_reduction",
            json.dumps({"reduction_percent": 25, "original_concurrency": 25, "new_concurrency": 19,
                        "reason": "CPU pressure sustained above 75% for 3 measurement windows"}),
            (now - timedelta(minutes=2)).isoformat(),
            "applied",
            "pending_measurement",
        ),
    )

    # -- Demo resource measurements (24 hourly, simulated) --
    base_hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=23)
    import random as _rnd
    _rnd.seed(42)  # deterministic seed data
    resource_scenarios = [
        # (cpu, mem, queue_depth, queue_wait_ms, active_jobs)
        (42, 54, 18, 120, 4), (44, 55, 20, 130, 5), (46, 56, 22, 140, 5),
        (48, 58, 24, 160, 6), (51, 61, 29, 200, 7), (55, 63, 35, 240, 8),
        (60, 65, 40, 280, 9), (65, 66, 48, 310, 10), (70, 67, 55, 360, 11),
        (78, 69, 63, 440, 12), (75, 68, 58, 410, 11), (72, 68, 52, 380, 10),
        (68, 67, 46, 340, 9), (64, 65, 40, 300, 8), (60, 63, 35, 260, 8),
        (57, 62, 31, 230, 7), (54, 61, 28, 200, 7), (52, 60, 25, 180, 6),
        (51, 59, 23, 165, 6), (50, 59, 22, 155, 5), (49, 58, 21, 148, 5),
        (48, 57, 20, 140, 5), (47, 57, 19, 133, 4), (46, 56, 18, 128, 4),
    ]
    for i, (cpu, mem, qdepth, qwait, ajobs) in enumerate(resource_scenarios):
        ts = (base_hour + timedelta(hours=i)).isoformat()
        await db.execute(
            """INSERT INTO resource_measurements
               (tenant_id, timestamp, cpu_percent, memory_percent, queue_depth,
                queue_wait_ms, active_jobs, scope, is_simulated)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (None, ts, cpu, mem, qdepth, qwait, ajobs, "machine", 1),
        )
        # Also seed per-tenant resource measurements for Northstar (the busy one)
        if cpu > 60:
            await db.execute(
                """INSERT INTO resource_measurements
                   (tenant_id, timestamp, cpu_percent, memory_percent, queue_depth,
                    queue_wait_ms, active_jobs, scope, is_simulated)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                ("tn_northstar_01", ts,
                 round(cpu * 0.7 + _rnd.uniform(-3, 3), 1),
                 round(mem * 0.6 + _rnd.uniform(-2, 2), 1),
                 max(0, qdepth - 10),
                 round(qwait * 0.8, 0), ajobs - 1,
                 "job-level-simulated", 1),
            )

    # -- Demo request events (simulated traffic for all tenants) --
    traffic_scenarios = [
        (4100, 180), (4300, 190), (4500, 200), (4700, 210), (4900, 220),
        (5200, 240), (5500, 260), (5800, 290), (6100, 330), (6800, 390),
        (7200, 430), (7600, 460), (7900, 480), (7600, 470), (7200, 440),
        (6800, 400), (6400, 370), (6100, 340), (5800, 310), (5500, 280),
        (5200, 260), (4900, 240), (4700, 220), (4500, 210),
    ]
    # Distribute traffic across the first 8 tenants proportionally
    priority_tenants = _TENANTS[:8]
    total_quota = sum(t["quota"] for t in priority_tenants)
    for i, (accepted, rejected) in enumerate(traffic_scenarios):
        ts = (base_hour + timedelta(hours=i)).isoformat()
        for t in priority_tenants:
            frac = t["quota"] / total_quota
            a_count = int(accepted * frac)
            r_count = int(rejected * frac)
            base_latency = 30 if t["workload"] == "API / light" else 80
            for _ in range(min(a_count, 8)):
                jitter = _rnd.uniform(-5, 15)
                await db.execute(
                    "INSERT INTO request_events (tenant_id, timestamp, status, latency_ms, is_simulated) VALUES (?,?,?,?,?)",
                    (t["id"], ts, "accepted", round(base_latency + jitter + i * 2, 1), 1),
                )
            for _ in range(min(r_count, 4)):
                await db.execute(
                    "INSERT INTO request_events (tenant_id, timestamp, status, latency_ms, reason, is_simulated) VALUES (?,?,?,?,?,?)",
                    (t["id"], ts, "rejected", 0, "rate_limit_exceeded", 1),
                )

    # -- Demo jobs and scheduling history --
    job_types_by_workload = {
        "CPU-intensive": ["compute_heavy", "data_crunch", "ml_batch"],
        "API / light": ["api_request", "health_check", "webhook"],
        "Batch jobs": ["batch_export", "etl_job", "report_gen"],
        "Mixed workload": ["api_request", "batch_export", "data_crunch"],
        "Streaming": ["stream_process", "event_ingest", "fanout"],
        "GPU compute": ["gpu_train", "inference_batch", "model_eval"],
        "ML inference": ["inference_single", "batch_inference", "model_serve"],
        "Real-time analytics": ["stream_agg", "alert_eval", "dashboard_query"],
        "e-commerce": ["order_checkout", "cart_sync", "catalog_search"],
        "gaming": ["matchmaking", "state_sync", "leaderboard_update"],
        "food-delivery": ["order_dispatch", "courier_track", "menu_fetch"],
    }
    sched_turn = 0
    active_tenants = _TENANTS[:10]
    for i, t in enumerate(active_tenants * 3):  # 30 demo jobs
        company_id = slug_to_id[t["company"]]
        cand_types = job_types_by_workload.get(t["workload"], ["generic_job", "data_sync", "batch_proc"])
        wtype = cand_types[i % len(cand_types)]
        created = (now - timedelta(minutes=30 - i)).isoformat()
        started = (now - timedelta(minutes=30 - i - 1)).isoformat()
        completed = (now - timedelta(minutes=30 - i - 2)).isoformat()
        qwait_ms = round(_rnd.uniform(50, 800), 1)
        exec_ms = round(_rnd.uniform(100, 3000), 1)
        worker = (i % 12) + 1
        sched_turn += 1
        cursor2 = await db.execute(
            """INSERT INTO jobs
               (tenant_id, job_type, status, priority, created_at, started_at, completed_at,
                duration_ms, queue_wait_ms, worker_id, is_simulated)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (t["id"], wtype, "completed", 5, created, started, completed,
             exec_ms, qwait_ms, worker, 1),
        )
        job_id = cursor2.lastrowid
        await db.execute(
            """INSERT INTO scheduling_history
               (job_id, tenant_id, company_id, event, scheduling_turn, queue_wait_ms,
                execution_ms, worker_id, result, decision_reason, timestamp)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (job_id, t["id"], company_id, "scheduled", sched_turn,
             qwait_ms, exec_ms, worker, "completed",
             f"Round-robin turn {sched_turn}: tenant {t['name']} selected from {len(active_tenants)} active queues",
             started),
        )

    # -- Demo experiment --
    await db.execute(
        """INSERT INTO experiments
           (tenant_id, name, scenario, status, config, started_at, completed_at,
            before_metrics, after_metrics, outcome, is_simulated)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            "tn_northstar_01",
            "Concurrency reduction impact test",
            "scenario_d",
            "completed",
            json.dumps({"action": "reduce_concurrency", "reduction_percent": 25, "duration_seconds": 120}),
            (now - timedelta(hours=2)).isoformat(),
            (now - timedelta(hours=2) + timedelta(minutes=4)).isoformat(),
            json.dumps({"p95_latency_ms": 226, "cpu_percent_simulated": 78,
                        "queue_depth": 63, "rejected_per_min": 510, "queue_wait_ms": 440}),
            json.dumps({"p95_latency_ms": 184, "cpu_percent_simulated": 53,
                        "queue_depth": 26, "rejected_per_min": 180, "queue_wait_ms": 180}),
            "improved",
            1,
        ),
    )
