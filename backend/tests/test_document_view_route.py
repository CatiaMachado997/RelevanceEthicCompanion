"""
Tests for GET /api/documents/{id}/view

Covers:
- 401 when no token provided
- 401 when token is invalid
- 404 when document does not exist for this user
- 404 when document exists but raw_content is NULL
- 200 with correct Content-Type, Content-Disposition: inline, and bytes body
- Auth via Bearer header
- Auth via ?token= query param (iframe path)
- Filename sanitisation in Content-Disposition header
"""

import io
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from routes.documents import router as documents_router

TEST_USER_ID = "00000000-0000-0000-0000-000000000099"
TEST_DOC_ID = "aaaaaaaa-0000-0000-0000-000000000001"
FAKE_TOKEN = "valid.fake.token"
PDF_BYTES = b"%PDF-1.4 fake pdf content for testing"


def make_app():
    app = FastAPI()
    app.include_router(documents_router)
    return app


def make_db_mock(row=None):
    """Return a mock for get_db_connection() context manager."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = row
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return mock_conn


def good_row(filename="report.pdf", content_type="application/pdf", raw=PDF_BYTES):
    return {
        "id": TEST_DOC_ID,
        "filename": filename,
        "content_type": content_type,
        "raw_content": raw,
    }


@pytest.fixture
def client():
    return TestClient(make_app(), raise_server_exceptions=False)


# ── Auth checks ─────────────────────────────────────────────────────────────

def test_view_no_token_returns_401(client):
    """No Authorization header and no ?token= param → 401."""
    with patch("routes.documents.get_db_connection", return_value=make_db_mock()):
        resp = client.get(f"/api/documents/{TEST_DOC_ID}/view")
    assert resp.status_code == 401


def test_view_invalid_token_returns_401(client):
    """Invalid JWT in Authorization header → 401."""
    with patch(
        "routes.documents.get_user_id_from_token",
        side_effect=HTTPException(status_code=401, detail="Invalid token"),
    ):
        resp = client.get(
            f"/api/documents/{TEST_DOC_ID}/view",
            headers={"Authorization": "Bearer bad.token.here"},
        )
    assert resp.status_code == 401


def test_view_auth_via_query_param(client):
    """Auth token passed as ?token= query param (iframe path) → accepted."""
    with patch(
        "routes.documents.get_user_id_from_token",
        return_value=TEST_USER_ID,
    ), patch(
        "routes.documents.get_db_connection",
        return_value=make_db_mock(row=good_row()),
    ):
        resp = client.get(f"/api/documents/{TEST_DOC_ID}/view?token={FAKE_TOKEN}")
    assert resp.status_code == 200


def test_view_auth_via_bearer_header(client):
    """Auth token in Authorization: Bearer header → accepted."""
    with patch(
        "routes.documents.get_user_id_from_token",
        return_value=TEST_USER_ID,
    ), patch(
        "routes.documents.get_db_connection",
        return_value=make_db_mock(row=good_row()),
    ):
        resp = client.get(
            f"/api/documents/{TEST_DOC_ID}/view",
            headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        )
    assert resp.status_code == 200


# ── 404 cases ────────────────────────────────────────────────────────────────

def test_view_document_not_found_returns_404(client):
    """Document not in DB (or wrong user) → 404."""
    with patch(
        "routes.documents.get_user_id_from_token",
        return_value=TEST_USER_ID,
    ), patch(
        "routes.documents.get_db_connection",
        return_value=make_db_mock(row=None),   # fetchone returns None
    ):
        resp = client.get(
            f"/api/documents/{TEST_DOC_ID}/view",
            headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_view_null_raw_content_returns_404(client):
    """Document exists but raw_content is NULL → 404."""
    row = good_row()
    row["raw_content"] = None
    with patch(
        "routes.documents.get_user_id_from_token",
        return_value=TEST_USER_ID,
    ), patch(
        "routes.documents.get_db_connection",
        return_value=make_db_mock(row=row),
    ):
        resp = client.get(
            f"/api/documents/{TEST_DOC_ID}/view",
            headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        )
    assert resp.status_code == 404
    assert "not available" in resp.json()["detail"].lower()


# ── Successful response ───────────────────────────────────────────────────────

def test_view_returns_pdf_bytes(client):
    """200 response body contains the raw PDF bytes."""
    with patch(
        "routes.documents.get_user_id_from_token",
        return_value=TEST_USER_ID,
    ), patch(
        "routes.documents.get_db_connection",
        return_value=make_db_mock(row=good_row()),
    ):
        resp = client.get(
            f"/api/documents/{TEST_DOC_ID}/view",
            headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        )
    assert resp.status_code == 200
    assert resp.content == PDF_BYTES


def test_view_content_type_header(client):
    """Response Content-Type matches the stored document content_type."""
    with patch(
        "routes.documents.get_user_id_from_token",
        return_value=TEST_USER_ID,
    ), patch(
        "routes.documents.get_db_connection",
        return_value=make_db_mock(row=good_row()),
    ):
        resp = client.get(
            f"/api/documents/{TEST_DOC_ID}/view",
            headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        )
    assert "application/pdf" in resp.headers["content-type"]


def test_view_content_disposition_inline(client):
    """Content-Disposition must be inline (not attachment) for in-browser rendering."""
    with patch(
        "routes.documents.get_user_id_from_token",
        return_value=TEST_USER_ID,
    ), patch(
        "routes.documents.get_db_connection",
        return_value=make_db_mock(row=good_row(filename="report.pdf")),
    ):
        resp = client.get(
            f"/api/documents/{TEST_DOC_ID}/view",
            headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        )
    disposition = resp.headers.get("content-disposition", "")
    assert disposition.startswith("inline")
    assert "report.pdf" in disposition


def test_view_content_type_fallback_to_octet_stream(client):
    """When content_type is NULL/empty, fallback is application/octet-stream (not pdf)."""
    row = good_row(content_type=None)
    with patch(
        "routes.documents.get_user_id_from_token",
        return_value=TEST_USER_ID,
    ), patch(
        "routes.documents.get_db_connection",
        return_value=make_db_mock(row=row),
    ):
        resp = client.get(
            f"/api/documents/{TEST_DOC_ID}/view",
            headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        )
    assert resp.status_code == 200
    assert "octet-stream" in resp.headers["content-type"]


# ── Filename sanitisation ─────────────────────────────────────────────────────

def test_view_sanitises_filename_quotes(client):
    """Double-quotes in filename are replaced to prevent header injection."""
    row = good_row(filename='evil"file.pdf')
    with patch(
        "routes.documents.get_user_id_from_token",
        return_value=TEST_USER_ID,
    ), patch(
        "routes.documents.get_db_connection",
        return_value=make_db_mock(row=row),
    ):
        resp = client.get(
            f"/api/documents/{TEST_DOC_ID}/view",
            headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        )
    disposition = resp.headers.get("content-disposition", "")
    # The double-quote should be replaced, not present as-is
    assert '"evil"' not in disposition
    assert "evil" in disposition  # filename still present, sanitised


def test_view_sanitises_filename_newlines(client):
    """Newlines in filename are stripped to prevent header injection."""
    row = good_row(filename="evil\r\ninjected: header\r\nfile.pdf")
    with patch(
        "routes.documents.get_user_id_from_token",
        return_value=TEST_USER_ID,
    ), patch(
        "routes.documents.get_db_connection",
        return_value=make_db_mock(row=row),
    ):
        resp = client.get(
            f"/api/documents/{TEST_DOC_ID}/view",
            headers={"Authorization": f"Bearer {FAKE_TOKEN}"},
        )
    disposition = resp.headers.get("content-disposition", "")
    assert "\r" not in disposition
    assert "\n" not in disposition
