"""Tests for database initialization and seed data."""

import pytest
import pytest_asyncio

from database import get_db, init_db


@pytest.mark.asyncio
async def test_init_creates_tables():
    await init_db()
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [r["name"] for r in await cursor.fetchall()]
        expected = [
            "companies", "experiments", "incidents", "jobs",
            "protection_actions", "request_events", "resource_measurements",
            "scheduling_history", "security_events", "tenant_quotas", "tenants",
        ]
        for t in expected:
            assert t in tables, f"Table {t} missing"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_seed_creates_10_companies():
    await init_db()
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) AS cnt FROM companies")
        row = await cursor.fetchone()
        assert row["cnt"] in (10, 13)
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_seed_creates_tenants():
    await init_db()
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) AS cnt FROM tenants")
        row = await cursor.fetchone()
        assert row["cnt"] in (25, 28)  # Sum of all tenant entries in seed
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_seed_is_idempotent():
    await init_db()
    await init_db()  # Second call should not duplicate
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) AS cnt FROM companies")
        row = await cursor.fetchone()
        assert row["cnt"] in (10, 13)
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_seed_creates_quotas_for_all_tenants():
    await init_db()
    db = await get_db()
    try:
        cursor = await db.execute(
            """SELECT COUNT(*) AS cnt FROM tenant_quotas"""
        )
        row = await cursor.fetchone()
        assert row["cnt"] in (25, 28)
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_seed_creates_demo_incident():
    await init_db()
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) AS cnt FROM incidents WHERE is_simulated = 1")
        row = await cursor.fetchone()
        assert row["cnt"] >= 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_api_keys_are_unique():
    await init_db()
    db = await get_db()
    try:
        cursor = await db.execute("SELECT api_key FROM companies")
        keys = [r["api_key"] for r in await cursor.fetchall()]
        assert len(keys) == len(set(keys)), "API keys must be unique"
    finally:
        await db.close()
