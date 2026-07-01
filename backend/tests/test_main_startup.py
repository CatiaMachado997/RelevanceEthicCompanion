"""Tests for backend startup behavior — auto-migrations on lifespan.

Sprint G Task 1: verify migrations run automatically on FastAPI startup, and
that a migration failure aborts startup (fail-loud, fail-forward) so we never
serve traffic against a stale schema.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def test_lifespan_calls_run_migrations():
    """Starting the app via TestClient should trigger run_migrations() exactly once."""
    stub = MagicMock(return_value=0)

    with patch("main.run_migrations", stub), patch(
        "utils.weaviate_client.get_weaviate_client", return_value=None
    ):
        from main import app

        with TestClient(app, raise_server_exceptions=False) as client:
            # Sanity ping so the app actually started
            client.get("/")

    assert (
        stub.call_count == 1
    ), f"expected run_migrations to be called once, got {stub.call_count}"


def test_lifespan_aborts_when_migration_fails():
    """If run_migrations raises, the app must refuse to start (fail loud)."""
    stub = MagicMock(side_effect=Exception("boom"))

    with patch("main.run_migrations", stub), patch(
        "utils.weaviate_client.get_weaviate_client", return_value=None
    ):
        from main import app

        with pytest.raises(Exception, match="boom"):
            with TestClient(app) as client:
                client.get("/")

    assert stub.called
