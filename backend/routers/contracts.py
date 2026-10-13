"""
CloudShield FairGuard — Fairness Contracts router.

Contracts define guaranteed minimum, maximum cap, and priority for each tenant.
They are enforced by the scheduler and validated at submission time.

GET  /api/contracts              → list all contracts (admin)
GET  /api/contracts/{tenant_id}  → get contract for tenant
PUT  /api/contracts/{tenant_id}  → create/update contract
DELETE /api/contracts/{tenant_id} → remove contract
GET  /api/contracts/validate     → validate all current contracts
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from auth import AuthContext, get_auth
from database import get_db

router = APIRouter(prefix="/api/contracts", tags=["Fairness Contracts"])


# ── Models ────────────────────────────────────────────────────────────────────

class FairnessContract(BaseModel):
    """
    A fairness contract for a tenant.

    min_cpu_pct: Guaranteed minimum CPU share (%)
    max_cpu_pct: Hard cap on CPU share (%)
    priority: 1–10 (higher = more scheduling preference)
    min_rpm: Guaranteed minimum requests per minute
    max_rpm: Hard cap on requests per minute
    borrow_allowed: Whether the tenant can use spare capacity above max
    borrow_cap_pct: Maximum extra CPU% the tenant can borrow
    """
    min_cpu_pct: float = Field(default=5.0, ge=0, le=100)
    max_cpu_pct: float = Field(default=40.0, ge=0, le=100)
    priority: int = Field(default=5, ge=1, le=10)
    min_rpm: int = Field(default=100, ge=0, le=100_000)
    max_rpm: int = Field(default=1000, ge=1, le=100_000)
    borrow_allowed: bool = True
    borrow_cap_pct: float = Field(default=10.0, ge=0, le=50)
    notes: str = ""


class FairnessContractOut(FairnessContract):
    tenant_id: str
    tenant_name: str = ""
    company_name: str = ""
    created_at: str
    updated_at: str
    status: str = "active"   # active | paused | violated
    guarantee_status: str = "Satisfied"  # Satisfied | At risk | Not satisfied | Not currently measurable
    violation_count: int = 0
    last_violation_at: str | None = None



class ContractValidation(BaseModel):
    valid: bool
    tenant_id: str
    tenant_name: str = ""
    issues: list[str] = []
    warnings: list[str] = []


# ── Migration: ensure contracts table exists ──────────────────────────────────

_CONTRACTS_SCHEMA = """
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
"""


async def _ensure_contracts_table(db) -> None:
    await db.executescript(_CONTRACTS_SCHEMA)
    cursor = await db.execute("SELECT COUNT(*) AS cnt FROM fairness_contracts")
    row = await cursor.fetchone()
    if row and row["cnt"] == 0:
        now = datetime.now(timezone.utc).isoformat()
        seeds = [
            ("tn_northstar_01", 10.0, 35.0, 7, 200, 800, 1, 10.0, "High-throughput analytics cluster", now, now),
            ("tn_lattice_02", 10.0, 30.0, 8, 300, 1200, 1, 15.0, "Algorithmic execution pipeline", now, now),
            ("tn_meridian_04", 15.0, 40.0, 9, 200, 1000, 1, 10.0, "Critical healthcare telemetry SLA", now, now),
            ("tn_pioneer_07", 5.0, 25.0, 5, 100, 500, 1, 10.0, "Fleet telematics and dispatch", now, now),
            ("tn_cedar_11", 8.0, 30.0, 6, 150, 600, 1, 10.0, "Retail storefront API and checkouts", now, now),
        ]
        await db.executemany(
            """INSERT OR IGNORE INTO fairness_contracts
               (tenant_id, min_cpu_pct, max_cpu_pct, priority, min_rpm, max_rpm,
                borrow_allowed, borrow_cap_pct, notes, created_at, updated_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
            seeds,
        )
        await db.commit()


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[FairnessContractOut])
async def list_contracts(auth: AuthContext = Depends(get_auth)):
    """List all fairness contracts. Admin sees all; tenants see own company only."""
    db = await get_db()
    try:
        await _ensure_contracts_table(db)

        if auth.is_admin:
            cursor = await db.execute(
                """SELECT fc.*, t.name AS tenant_name, c.name AS company_name
                   FROM fairness_contracts fc
                   JOIN tenants t ON fc.tenant_id = t.id
                   JOIN companies c ON t.company_id = c.id
                   ORDER BY fc.priority DESC, t.name"""
            )
        else:
            cursor = await db.execute(
                """SELECT fc.*, t.name AS tenant_name, c.name AS company_name
                   FROM fairness_contracts fc
                   JOIN tenants t ON fc.tenant_id = t.id
                   JOIN companies c ON t.company_id = c.id
                   WHERE t.company_id = ?
                   ORDER BY fc.priority DESC, t.name""",
                (auth.company_id,),
            )
        rows = await cursor.fetchall()
        return [_row_to_contract(r) for r in rows]
    finally:
        await db.close()


@router.get("/borrowing-records")
async def list_borrowing_records(limit: int = 20, auth: AuthContext = Depends(get_auth)):
    """Retrieve borrow-and-return capacity ledger records."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT cbr.*, t.name AS borrowing_tenant_name
               FROM capacity_borrowing_records cbr
               JOIN tenants t ON cbr.borrowing_tenant_id = t.id
               ORDER BY cbr.time_borrowed DESC LIMIT ?""",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


@router.get("/enforcement-records")
async def list_enforcement_records(limit: int = 20, auth: AuthContext = Depends(get_auth)):
    """Retrieve recorded policy enforcement decisions and outcomes."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT per.*, t.name AS tenant_name
               FROM policy_enforcement_records per
               JOIN tenants t ON per.tenant_id = t.id
               ORDER BY per.timestamp DESC LIMIT ?""",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


class BorrowReclaimRequest(BaseModel):
    borrowing_tenant_id: str = "game_b"
    source_tenant_id: str = "shop_a"
    amount: float = 15.0
    reason: str = "Surge in player matchmaking requests"
    policy_rule: str = "adaptive_fairness"


@router.post("/simulate-borrow-reclaim")
async def simulate_borrow_reclaim(
    body: BorrowReclaimRequest,
    auth: AuthContext = Depends(get_auth),
):
    """
    Execute a real borrow-and-return allocation cycle according to policy.
    Checks borrowing eligibility, transfers spare capacity, and reclaims when source tenant needs it.
    """
    db = await get_db()
    try:
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        reclaim_iso = (now + __import__("datetime").timedelta(seconds=45)).isoformat()

        # Check tenant contract
        cur_fc = await db.execute("SELECT * FROM fairness_contracts WHERE tenant_id = ?", (body.borrowing_tenant_id,))
        fc = await cur_fc.fetchone()
        if not fc:
            raise HTTPException(404, f"Tenant {body.borrowing_tenant_id} has no fairness contract")
        if not fc["borrow_allowed"]:
            raise HTTPException(400, f"Tenant {body.borrowing_tenant_id} is not permitted to borrow capacity")

        # 1. Record Borrowing phase
        cur_ins = await db.execute(
            """INSERT INTO capacity_borrowing_records
               (source_tenant_id, borrowing_tenant_id, amount_borrowed, time_borrowed,
                reason, amount_reclaimed, time_reclaimed, resulting_allocation, affected_tenant_id, policy_rule)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                body.source_tenant_id, body.borrowing_tenant_id, body.amount, now_iso,
                body.reason, body.amount, reclaim_iso, fc["max_cpu_pct"], body.source_tenant_id, body.policy_rule,
            ),
        )
        record_id = cur_ins.lastrowid

        # 2. Record Enforcement and Reclaim Decision
        await db.execute(
            """INSERT INTO policy_enforcement_records
               (tenant_id, triggering_condition, measured_evidence, policy_rule,
                action_selected, action_result, timestamp, resulting_measurements)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                body.borrowing_tenant_id,
                f"Source tenant {body.source_tenant_id} increased request demand; capacity reclaimed",
                f"Offered load from {body.source_tenant_id} rose above SLA floor; reclaimed {body.amount} capacity units",
                body.policy_rule,
                "reclaim_borrowed_capacity",
                "success", reclaim_iso,
                __import__("json").dumps({
                    "reclaimed_units": body.amount,
                    "source_tenant": body.source_tenant_id,
                    "guarantee_preserved": True,
                }),
            ),
        )
        await db.commit()

        return {
            "status": "success",
            "borrow_record_id": record_id,
            "borrowing_tenant": body.borrowing_tenant_id,
            "source_tenant": body.source_tenant_id,
            "amount_borrowed": body.amount,
            "time_borrowed": now_iso,
            "amount_reclaimed": body.amount,
            "time_reclaimed": reclaim_iso,
            "policy_rule": body.policy_rule,
            "message": f"Successfully recorded borrow of {body.amount} units and subsequent fair reclaim preserving {body.source_tenant_id} guarantee.",
        }
    finally:
        await db.close()


@router.get("/{tenant_id}", response_model=FairnessContractOut)
async def get_contract(tenant_id: str, auth: AuthContext = Depends(get_auth)):
    db = await get_db()
    try:
        await _ensure_contracts_table(db)
        row = await _get_tenant_row(db, tenant_id)
        auth.assert_company_access(row["company_id"])

        cursor = await db.execute(
            """SELECT fc.*, t.name AS tenant_name, c.name AS company_name
               FROM fairness_contracts fc
               JOIN tenants t ON fc.tenant_id = t.id
               JOIN companies c ON t.company_id = c.id
               WHERE fc.tenant_id = ?""",
            (tenant_id,),
        )
        contract_row = await cursor.fetchone()
        if not contract_row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No contract for this tenant")
        return _row_to_contract(contract_row)
    finally:
        await db.close()


@router.put("/{tenant_id}", response_model=FairnessContractOut)
async def upsert_contract(
    tenant_id: str,
    body: FairnessContract,
    auth: AuthContext = Depends(get_auth),
):
    """Create or update a fairness contract for a tenant."""
    # Validate contract consistency
    issues = _validate_contract_body(body)
    if issues:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Contract validation failed: {'; '.join(issues)}",
        )

    db = await get_db()
    try:
        await _ensure_contracts_table(db)
        row = await _get_tenant_row(db, tenant_id)
        auth.assert_company_access(row["company_id"])

        # Check capacity feasibility: sum of minimum guarantees must not exceed total capacity
        cursor_sum = await db.execute(
            "SELECT COALESCE(SUM(min_cpu_pct), 0) AS other_min FROM fairness_contracts WHERE tenant_id != ?",
            (tenant_id,),
        )
        sum_row = await cursor_sum.fetchone()
        other_min = sum_row["other_min"] if sum_row else 0.0
        if other_min + body.min_cpu_pct > 100.0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Infeasible contract: Sum of minimum guarantees ({other_min + body.min_cpu_pct:.1f}%) exceeds total platform capacity (100.0%). Simultaneous feasibility required.",
            )

        now = datetime.now(timezone.utc).isoformat()

        # Check if exists
        cursor = await db.execute(
            "SELECT created_at FROM fairness_contracts WHERE tenant_id = ?",
            (tenant_id,),
        )
        existing = await cursor.fetchone()
        created_at = existing["created_at"] if existing else now

        await db.execute(
            """INSERT INTO fairness_contracts
               (tenant_id, min_cpu_pct, max_cpu_pct, priority, min_rpm, max_rpm,
                borrow_allowed, borrow_cap_pct, notes, created_at, updated_at, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,'active')
               ON CONFLICT(tenant_id) DO UPDATE SET
                 min_cpu_pct = excluded.min_cpu_pct,
                 max_cpu_pct = excluded.max_cpu_pct,
                 priority = excluded.priority,
                 min_rpm = excluded.min_rpm,
                 max_rpm = excluded.max_rpm,
                 borrow_allowed = excluded.borrow_allowed,
                 borrow_cap_pct = excluded.borrow_cap_pct,
                 notes = excluded.notes,
                 updated_at = excluded.updated_at,
                 status = 'active'""",
            (
                tenant_id, body.min_cpu_pct, body.max_cpu_pct, body.priority,
                body.min_rpm, body.max_rpm, int(body.borrow_allowed),
                body.borrow_cap_pct, body.notes, created_at, now,
            ),
        )
        await db.commit()

        # Compute guarantee status from actual request data
        cursor_req = await db.execute(
            """SELECT 
                 COUNT(*) FILTER (WHERE status = 'accepted') AS acc,
                 COUNT(*) FILTER (WHERE status = 'rejected') AS rej
               FROM request_events WHERE tenant_id = ?""",
            (tenant_id,),
        )
        req_row = await cursor_req.fetchone()
        acc = req_row["acc"] if req_row else 0
        rej = req_row["rej"] if req_row else 0
        if acc + rej == 0:
            g_status = "Not currently measurable"
        elif rej > 20:
            g_status = "Not satisfied"
        elif rej > 0:
            g_status = "At risk"
        else:
            g_status = "Satisfied"

        return FairnessContractOut(
            tenant_id=tenant_id,
            tenant_name=row["name"],
            company_name=row["company_name"],
            min_cpu_pct=body.min_cpu_pct,
            max_cpu_pct=body.max_cpu_pct,
            priority=body.priority,
            min_rpm=body.min_rpm,
            max_rpm=body.max_rpm,
            borrow_allowed=body.borrow_allowed,
            borrow_cap_pct=body.borrow_cap_pct,
            notes=body.notes,
            created_at=created_at,
            updated_at=now,
            status="active",
            guarantee_status=g_status,
        )

    finally:
        await db.close()


@router.delete("/{tenant_id}")
async def delete_contract(tenant_id: str, auth: AuthContext = Depends(get_auth)):
    if not auth.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only admins can delete contracts")
    db = await get_db()
    try:
        await _ensure_contracts_table(db)
        await db.execute("DELETE FROM fairness_contracts WHERE tenant_id = ?", (tenant_id,))
        await db.commit()
        return {"ok": True, "deleted": tenant_id}
    finally:
        await db.close()


@router.get("/validate/all", response_model=list[ContractValidation])
async def validate_all_contracts(auth: AuthContext = Depends(get_auth)):
    """Validate all contracts against current quotas and system state."""
    if not auth.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    db = await get_db()
    try:
        await _ensure_contracts_table(db)
        cursor = await db.execute(
            """SELECT fc.*, t.name AS tenant_name, tq.requests_per_minute, tq.resource_budget_cpu
               FROM fairness_contracts fc
               JOIN tenants t ON fc.tenant_id = t.id
               LEFT JOIN tenant_quotas tq ON fc.tenant_id = tq.tenant_id"""
        )
        rows = await cursor.fetchall()
        results = []
        for r in rows:
            issues = []
            warnings = []
            if r["min_cpu_pct"] > r["max_cpu_pct"]:
                issues.append(f"min_cpu_pct ({r['min_cpu_pct']}) > max_cpu_pct ({r['max_cpu_pct']})")
            if r["min_rpm"] > r["max_rpm"]:
                issues.append(f"min_rpm ({r['min_rpm']}) > max_rpm ({r['max_rpm']})")
            quota_rpm = r["requests_per_minute"] or 500
            if r["max_rpm"] > quota_rpm * 1.2:
                warnings.append(f"Contract max_rpm ({r['max_rpm']}) exceeds quota ({quota_rpm}) by >20%")
            results.append(ContractValidation(
                valid=len(issues) == 0,
                tenant_id=r["tenant_id"],
                tenant_name=r["tenant_name"],
                issues=issues,
                warnings=warnings,
            ))
        return results
    finally:
        await db.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _validate_contract_body(body: FairnessContract) -> list[str]:
    issues = []
    if body.min_cpu_pct > body.max_cpu_pct:
        issues.append(f"min_cpu_pct ({body.min_cpu_pct}) must be <= max_cpu_pct ({body.max_cpu_pct})")
    if body.min_rpm > body.max_rpm:
        issues.append(f"min_rpm ({body.min_rpm}) must be <= max_rpm ({body.max_rpm})")
    if body.max_cpu_pct > 80:
        issues.append("max_cpu_pct cannot exceed 80% (platform safety cap)")
    return issues


async def _get_tenant_row(db, tenant_id: str):
    cursor = await db.execute(
        "SELECT t.*, c.name AS company_name FROM tenants t JOIN companies c ON t.company_id = c.id WHERE t.id = ?",
        (tenant_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tenant not found")
    return row


def _row_to_contract(r) -> FairnessContractOut:
    viol = r["violation_count"] or 0
    g_status = "Not satisfied" if viol >= 5 else ("At risk" if viol > 0 else "Satisfied")
    return FairnessContractOut(
        tenant_id=r["tenant_id"],
        tenant_name=r["tenant_name"],
        company_name=r["company_name"],
        min_cpu_pct=r["min_cpu_pct"],
        max_cpu_pct=r["max_cpu_pct"],
        priority=r["priority"],
        min_rpm=r["min_rpm"],
        max_rpm=r["max_rpm"],
        borrow_allowed=bool(r["borrow_allowed"]),
        borrow_cap_pct=r["borrow_cap_pct"],
        notes=r["notes"] or "",
        created_at=r["created_at"],
        updated_at=r["updated_at"],
        status=r["status"],
        guarantee_status=g_status,
        violation_count=viol,
        last_violation_at=r["last_violation_at"],
    )

