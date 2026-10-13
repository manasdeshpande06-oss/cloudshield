"""
CloudShield FairGuard — Authentication router.

Provides JWT-based login for admin and tenant users.
Admins use a fixed platform key. Tenants log in with
their company API key which grants company-scoped access.

POST /api/auth/login   → { access_token, token_type, role, user }
POST /api/auth/logout  → { ok: true }
GET  /api/auth/me      → current user info
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from database import PLATFORM_ADMIN_KEY, get_db

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# ── JWT config ────────────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get(
    "FAIRGUARD_JWT_SECRET",
    "f4!rGu@rd-2024-hackathon-secret-do-not-use-in-prod",
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 hours — generous for demo

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ── Pydantic models ───────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    company_id: str | None = None
    company_name: str | None = None
    company_slug: str | None = None
    display_name: str
    expires_in: int


class UserInfo(BaseModel):
    role: str
    company_id: str | None = None
    company_name: str | None = None
    company_slug: str | None = None
    display_name: str
    api_key_hint: str = ""


# ── Token helpers ─────────────────────────────────────────────────────────────

def _create_token(data: dict[str, Any], expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Token invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """
    Authenticate and return a JWT.
    - username='admin', password=<PLATFORM_ADMIN_KEY>  admin role
    - username=<company_slug>, password=<company_api_key>  tenant role
    """
    username = body.username.strip()
    password = body.password.strip()

    # Admin login
    if username == "admin" and password in (PLATFORM_ADMIN_KEY, "admin"):
        token = _create_token(
            {"sub": "admin", "role": "admin"},
            timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        return TokenResponse(
            access_token=token,
            role="admin",
            display_name="Platform Admin",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    # Tenant login (by slug + api_key OR slug + slug OR api_key)
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT id, name, slug, api_key FROM companies WHERE slug = ? OR api_key = ? OR name = ?",
            (username.lower(), username, username),
        )
        row = await cursor.fetchone()

        if row is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

        # Accept registered api_key, company slug, or 'password'
        if password != row["api_key"] and password != row["slug"] and password != "password":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

        token = _create_token(
            {
                "sub": row["id"],
                "role": "tenant",
                "company_id": row["id"],
                "company_name": row["name"],
                "company_slug": row["slug"],
            },
            timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        return TokenResponse(
            access_token=token,
            role="tenant",
            company_id=row["id"],
            company_name=row["name"],
            company_slug=row["slug"],
            display_name=row["name"],
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    finally:
        await db.close()


@router.post("/logout")
async def logout():
    return {"ok": True, "message": "Logged out. Please discard your token."}


@router.get("/me", response_model=UserInfo)
async def get_me(token: str | None = Depends(oauth2_scheme)):
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    payload = _decode_token(token)
    role = payload.get("role", "tenant")

    if role == "admin":
        return UserInfo(
            role="admin",
            display_name="Platform Admin",
            api_key_hint=PLATFORM_ADMIN_KEY[:8] + "...",
        )

    return UserInfo(
        role="tenant",
        company_id=payload.get("company_id"),
        company_name=payload.get("company_name"),
        company_slug=payload.get("company_slug"),
        display_name=payload.get("company_name", "Tenant"),
    )


@router.get("/credentials")
async def list_demo_credentials():
    """Return demo login credentials for the hackathon demo."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT name, slug, api_key FROM companies 
               ORDER BY CASE 
                 WHEN slug = 'shop_a' THEN 1 
                 WHEN slug = 'game_b' THEN 2 
                 WHEN slug = 'food_c' THEN 3 
                 WHEN slug = 'northstar' THEN 4
                 WHEN slug = 'meridian' THEN 5
                 ELSE 10 
               END, name LIMIT 8"""
        )
        rows = await cursor.fetchall()
        tenants = [
            {
                "company": r["name"],
                "username": r["slug"],
                "password": r["slug"] if r["slug"] in ("shop_a", "game_b", "food_c") else r["api_key"],
                "role": "tenant",
            }
            for r in rows
        ]
    finally:
        await db.close()

    return {
        "demo_credentials": [
            {
                "company": "CloudShield Platform",
                "username": "admin",
                "password": "admin",
                "role": "admin",
            },
            *tenants,
        ],
        "note": "Use these credentials on the /login page.",
    }


class RegisterRequest(BaseModel):
    company_name: str
    company_slug: str | None = None
    initial_tenant_name: str | None = None
    workload_type: str = "API / light"
    contact_email: str | None = None


@router.post("/register", response_model=TokenResponse)
async def register_tenant(body: RegisterRequest):
    """Self-registration for new tenants. Creates company, tenant, quota, and returns JWT."""
    name = body.company_name.strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Company name is required")

    import re
    import secrets

    slug = body.company_slug.strip().lower() if body.company_slug else re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        slug = f"tenant-{secrets.token_hex(4)}"

    db = await get_db()
    try:
        # Check uniqueness
        cursor = await db.execute("SELECT id FROM companies WHERE slug = ? OR name = ?", (slug, name))
        if await cursor.fetchone():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Company '{name}' or slug '{slug}' already exists")

        # Generate IDs
        import uuid
        now_iso = datetime.now(timezone.utc).isoformat()
        company_id = f"COMP-{secrets.token_hex(4).upper()}"
        api_key = f"fg_demo_{secrets.token_hex(8)}"

        await db.execute(
            "INSERT INTO companies (id, name, slug, api_key, registered_at, status) VALUES (?,?,?,?,?,?)",
            (company_id, name, slug, api_key, now_iso, "active"),
        )

        tenant_name = body.initial_tenant_name.strip() if body.initial_tenant_name else f"{name} Primary"
        tenant_id = f"tn_{slug[:12]}_{secrets.token_hex(2)}"

        await db.execute(
            "INSERT INTO tenants (id, company_id, name, workload_type, status, created_at) VALUES (?,?,?,?,?,?)",
            (tenant_id, company_id, tenant_name, body.workload_type, "healthy", now_iso),
        )

        await db.execute(
            """INSERT INTO tenant_quotas
               (tenant_id, requests_per_minute, max_concurrency, queue_limit,
                resource_budget_cpu, resource_budget_memory, window_seconds, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (tenant_id, 500, 25, 100, 25.0, 25.0, 60, now_iso),
        )

        # Create fairness contract
        await db.execute(
            """INSERT OR IGNORE INTO fairness_contracts
               (tenant_id, min_cpu_pct, max_cpu_pct, priority, min_rpm, max_rpm,
                borrow_allowed, borrow_cap_pct, notes, created_at, updated_at, status)
               VALUES (?, 10.0, 35.0, 5, 150, 750, 1, 10.0, 'Default onboarding contract', ?, ?, 'active')""",
            (tenant_id, now_iso, now_iso),
        )

        await db.commit()

        token = _create_token(
            {
                "sub": company_id,
                "role": "tenant",
                "company_id": company_id,
                "company_name": name,
                "company_slug": slug,
            },
            timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )

        return TokenResponse(
            access_token=token,
            role="tenant",
            company_id=company_id,
            company_name=name,
            company_slug=slug,
            display_name=name,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    finally:
        await db.close()

