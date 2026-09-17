"""Test configuration.

pytest imports conftest before any test module, so this is the one reliable place to
set environment before `app.config.settings` freezes (settings is read once at import).
Uses an isolated temp SQLite DB and a known admin email for the platform tests.
"""
from __future__ import annotations

import os
import tempfile

_TMP = tempfile.mkdtemp()
os.environ.setdefault("JALEBI_DATABASE_URL", f"sqlite+aiosqlite:///{_TMP}/test.db")
os.environ.setdefault("JALEBI_ADMIN_EMAILS", "founder@ties.org")
os.environ.setdefault("JALEBI_ALLOW_DEV_LOGIN", "true")
# Tests always use the deterministic mock (ignore any local .env provider/keys).
os.environ["JALEBI_PROVIDER"] = "mock"
# The workflow tests drive a document through the whole production loop, which is
# well over the 60/min default. The limiter has its own dedicated tests in
# test_hardening.py, which construct it directly.
os.environ.setdefault("JALEBI_RATE_LIMIT", "0")
