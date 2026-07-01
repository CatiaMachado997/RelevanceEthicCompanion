#!/usr/bin/env python3
"""CI-only: trigger the FastAPI lifespan once against a fresh database.

`main.py`'s lifespan creates the V4+ tables (documents, projects, tasks,
etc.) and then runs pending SQL migrations — the same self-healing bootstrap
every local/production deployment goes through on first start. CI's Postgres
service container starts empty, so this runs that bootstrap once before the
test suite so every test file sees a fully migrated schema regardless of
run order.

Usage:
    python scripts/ci_bootstrap.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

with TestClient(app):
    pass
