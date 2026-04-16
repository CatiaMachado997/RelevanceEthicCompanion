import pytest
from unittest.mock import patch, MagicMock


def _permission_row(trust_level: str):
    return {"trust_level": trust_level}


@pytest.mark.asyncio
async def test_ask_trust_returns_pending():
    """trust_level='ask' → PENDING_CONFIRMATION with preview."""
    from esl.tool_gate import ESLToolGate, GateResult

    gate = ESLToolGate()
    with patch("esl.tool_gate.get_db_connection") as mock_db:
        conn = MagicMock()
        cur = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchone.return_value = None  # no record → ask by default
        mock_db.return_value = conn

        result = await gate.check(
            user_id="u1",
            tool_id="github",
            action_name="create_issue",
            risk_level="medium",
            preview="Create issue: Fix login bug",
        )

    assert result.status == GateResult.PENDING_CONFIRMATION
    assert "Fix login bug" in result.preview


@pytest.mark.asyncio
async def test_explicit_ask_record_returns_pending():
    """trust_level='ask' stored in DB → PENDING_CONFIRMATION."""
    from esl.tool_gate import ESLToolGate, GateResult

    gate = ESLToolGate()
    with patch("esl.tool_gate.get_db_connection") as mock_db:
        conn = MagicMock()
        cur = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchone.return_value = {"trust_level": "ask"}  # explicit ask record
        mock_db.return_value = conn

        result = await gate.check(
            user_id="u1",
            tool_id="github",
            action_name="create_issue",
            risk_level="medium",
            preview="Create issue: Fix login bug",
        )

    assert result.status == GateResult.PENDING_CONFIRMATION
    assert "Fix login bug" in result.preview


@pytest.mark.asyncio
async def test_allow_trust_returns_approved():
    """trust_level='allow' and risk!='high' → APPROVED."""
    from esl.tool_gate import ESLToolGate, GateResult

    gate = ESLToolGate()
    with patch("esl.tool_gate.get_db_connection") as mock_db:
        conn = MagicMock()
        cur = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchone.return_value = _permission_row("allow")
        mock_db.return_value = conn

        result = await gate.check(
            user_id="u1",
            tool_id="github",
            action_name="create_issue",
            risk_level="medium",
            preview="Create issue",
        )

    assert result.status == GateResult.APPROVED


@pytest.mark.asyncio
async def test_deny_trust_returns_vetoed():
    """trust_level='deny' → VETOED regardless of risk level."""
    from esl.tool_gate import ESLToolGate, GateResult

    gate = ESLToolGate()
    with patch("esl.tool_gate.get_db_connection") as mock_db:
        conn = MagicMock()
        cur = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchone.return_value = _permission_row("deny")
        mock_db.return_value = conn

        result = await gate.check(
            user_id="u1",
            tool_id="github",
            action_name="create_issue",
            risk_level="medium",
            preview="Create issue",
        )

    assert result.status == GateResult.VETOED


@pytest.mark.asyncio
async def test_high_risk_always_pending_even_when_allowed():
    """risk_level='high' → PENDING_CONFIRMATION even when trust is 'allow'."""
    from esl.tool_gate import ESLToolGate, GateResult

    gate = ESLToolGate()
    with patch("esl.tool_gate.get_db_connection") as mock_db:
        conn = MagicMock()
        cur = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchone.return_value = _permission_row("allow")
        mock_db.return_value = conn

        result = await gate.check(
            user_id="u1",
            tool_id="gmail_write",
            action_name="send_reply",
            risk_level="high",
            preview="Send email to alice@example.com",
        )

    assert result.status == GateResult.PENDING_CONFIRMATION


@pytest.mark.asyncio
async def test_low_risk_no_record_auto_approved():
    """risk_level='low' with no permission record → APPROVED (auto-approve low risk)."""
    from esl.tool_gate import ESLToolGate, GateResult

    gate = ESLToolGate()
    with patch("esl.tool_gate.get_db_connection") as mock_db:
        conn = MagicMock()
        cur = MagicMock()
        conn.__enter__ = MagicMock(return_value=conn)
        conn.__exit__ = MagicMock(return_value=False)
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        cur.fetchone.return_value = None  # no record
        mock_db.return_value = conn

        result = await gate.check(
            user_id="u1",
            tool_id="notion",
            action_name="create_page",
            risk_level="low",
            preview="Create page: Meeting notes",
        )

    assert result.status == GateResult.APPROVED
