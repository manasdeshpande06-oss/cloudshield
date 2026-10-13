"""Shared test fixtures."""

from __future__ import annotations

import os
import sys
import tempfile

import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def _use_temp_db(tmp_path, monkeypatch):
    """Use a fresh temporary database for every test."""
    db_path = str(tmp_path / "test_fairguard.db")
    monkeypatch.setenv("FAIRGUARD_DB", db_path)
    # Patch the module-level DB_PATH used by database.py
    import database
    monkeypatch.setattr(database, "DB_PATH", db_path)


@pytest.fixture
def admin_headers():
    return {"Authorization": "Bearer fg_admin_platform_demo_key"}
