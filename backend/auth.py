"""
CloudShield FairGuard — API key authentication and company-scoped authorization.

Every request must include an ``Authorization: Bearer <api_key>`` header.
The platform admin key grants access to all companies and tenants.
A company-scoped key only grants access to that company's tenants.
"""

from __future__ import annotations

import os
from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt

from database import PLATFORM_ADMIN_KEY, get_db

SECRET_KEY = os.environ.get(
    "FAIRGUARD_JWT_SECRET",
    "f4!rGu@rd-2024-hackathon-secret-do-not-use-in-prod",
)
ALGORITHM = "HS256"


async def _resolve_api_key(
    authorization: str = Header(..., description="Bearer <api_key_or_jwt>"),
) -> tuple[str | None, bool]:
    """Return ``(company_id | None, is_admin)`` for the given bearer token or API key.

    Supports both JWT session tokens and static API keys.
    Raises 401 if the token/key is invalid.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing Bearer token")
    key = authorization.removeprefix("Bearer ").strip()

    # 1. Try decoding as JWT token
    try:
        payload = jwt.decode(key, SECRET_KEY, algorithms=[ALGORITHM])
        role = payload.get("role")
        if role == "admin":
            return None, True
        company_id = payload.get("company_id")
        return company_id, False
    except JWTError:
        pass  # Not a valid JWT, proceed to static key check

    # 2. Platform admin API key
    if key == PLATFORM_ADMIN_KEY:
        return None, True

    # 3. Company API key
    db = await get_db()
    try:
        cursor = await db.execute("SELECT id FROM companies WHERE api_key = ?", (key,))
        row = await cursor.fetchone()
    finally:
        await db.close()

    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key or session token")

    return row["id"], False


class AuthContext:
    """Resolved auth context injected into route handlers."""

    def __init__(self, company_id: str | None, is_admin: bool):
        self.company_id = company_id
        self.is_admin = is_admin

    def assert_admin(self) -> None:
        """Raise 403 if caller is not an administrator."""
        if not self.is_admin:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Access denied: platform administrator privileges required",
            )

    def assert_company_access(self, target_company_id: str) -> None:
        """Raise 403 if the caller does not have access to *target_company_id*."""
        if self.is_admin:
            return
        if self.company_id != target_company_id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Access denied: credentials do not grant access to this company",
            )

    def assert_tenant_access_by_company(self, tenant_company_id: str) -> None:
        """Same as assert_company_access but named for clarity at call sites."""
        self.assert_company_access(tenant_company_id)

    def company_filter(self) -> str | None:
        """Return the company_id to filter by, or None for admins (no filter)."""
        return self.company_id


async def get_auth(
    authorization: str | None = Header(default=None),
) -> AuthContext:
    """FastAPI dependency that authenticates and returns an AuthContext."""
    if not authorization:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing Authorization header")
    company_id, is_admin = await _resolve_api_key(authorization)
    return AuthContext(company_id, is_admin)


async def require_admin(auth: AuthContext = Depends(get_auth)) -> AuthContext:
    """FastAPI dependency that requires admin role."""
    auth.assert_admin()
    return auth

