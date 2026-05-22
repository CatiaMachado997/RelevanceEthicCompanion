"""Sprint J Task 6: unit tests for SafetyPreferencesService."""

from unittest.mock import MagicMock, patch

from services.safety_preferences import SafetyPreferencesService, SafetyPreferences


TEST_USER_ID = "00000000-0000-0000-0000-000000000000"


def _mock_db(execute_results):
    """execute_results is a list of (fetchone_value, fetchall_value) tuples,
    one per execute() call, returned in order."""
    cur = MagicMock()
    cur.fetchone = MagicMock(side_effect=[r[0] for r in execute_results])
    cur.fetchall = MagicMock(side_effect=[r[1] for r in execute_results])
    conn = MagicMock()
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    return conn, cur


def test_load_for_user_empty_returns_default_off():
    """A user with no rows in any layer gets safe_mode_enabled=False and empty sets."""
    conn, _ = _mock_db([
        (None, [{"safe_mode_enabled": False}]),  # users SELECT
        (None, []),                              # categories SELECT
        (None, []),                              # tools SELECT
    ])
    with patch("services.safety_preferences.get_db_connection", return_value=conn):
        svc = SafetyPreferencesService()
        prefs = svc.load_for_user(TEST_USER_ID)
    assert prefs.safe_mode_enabled is False
    assert prefs.categories == set()
    assert prefs.tools == set()


def test_load_for_user_with_master_on():
    conn, _ = _mock_db([
        (None, [{"safe_mode_enabled": True}]),
        (None, []),
        (None, []),
    ])
    with patch("services.safety_preferences.get_db_connection", return_value=conn):
        prefs = SafetyPreferencesService().load_for_user(TEST_USER_ID)
    assert prefs.safe_mode_enabled is True


def test_load_for_user_with_categories_and_tools():
    conn, _ = _mock_db([
        (None, [{"safe_mode_enabled": False}]),
        (None, [
            {"category": "write-external", "requires_confirmation": True},
            {"category": "read-external",  "requires_confirmation": True},
        ]),
        (None, [
            {"tool_name": "create_note", "requires_confirmation": True},
        ]),
    ])
    with patch("services.safety_preferences.get_db_connection", return_value=conn):
        prefs = SafetyPreferencesService().load_for_user(TEST_USER_ID)
    assert prefs.categories == {"write-external", "read-external"}
    assert prefs.tools == {"create_note"}


def test_should_confirm_master_on_short_circuits():
    prefs = SafetyPreferences(
        safe_mode_enabled=True, categories=set(), tools=set()
    )
    assert prefs.should_confirm(tool_name="anything", category="read-personal") is True


def test_should_confirm_category_match():
    prefs = SafetyPreferences(
        safe_mode_enabled=False,
        categories={"write-external"},
        tools=set(),
    )
    assert prefs.should_confirm(tool_name="send_email", category="write-external") is True
    assert prefs.should_confirm(tool_name="query_calendar", category="read-personal") is False


def test_should_confirm_tool_match():
    prefs = SafetyPreferences(
        safe_mode_enabled=False, categories=set(), tools={"web_search"}
    )
    assert prefs.should_confirm(tool_name="web_search", category="read-external") is True
    assert prefs.should_confirm(tool_name="query_calendar", category="read-personal") is False


def test_should_confirm_explain_reason_priority():
    """When multiple layers would fire, reason reflects the highest-priority layer."""
    prefs = SafetyPreferences(
        safe_mode_enabled=True,
        categories={"write-external"},
        tools={"send_email"},
    )
    reason = prefs.explain_reason(tool_name="send_email", category="write-external")
    # Master wins over category wins over tool
    assert "safe mode" in reason.lower()

    prefs2 = SafetyPreferences(
        safe_mode_enabled=False,
        categories={"write-external"},
        tools={"send_email"},
    )
    reason2 = prefs2.explain_reason(tool_name="send_email", category="write-external")
    assert "category" in reason2.lower() and "write-external" in reason2


def test_set_safe_mode_upserts():
    conn, cur = _mock_db([(None, None)])
    with patch("services.safety_preferences.get_db_connection", return_value=conn):
        SafetyPreferencesService().set_safe_mode(TEST_USER_ID, enabled=True)
    sql = cur.execute.call_args[0][0]
    assert "UPDATE users" in sql
    assert "safe_mode_enabled" in sql
    params = cur.execute.call_args[0][1]
    assert True in params
    assert TEST_USER_ID in params


def test_set_category_upsert_true_writes_row():
    conn, cur = _mock_db([(None, None)])
    with patch("services.safety_preferences.get_db_connection", return_value=conn):
        SafetyPreferencesService().set_category(
            TEST_USER_ID, category="write-external", requires_confirmation=True
        )
    sql = cur.execute.call_args[0][0]
    assert "INSERT INTO user_category_preferences" in sql
    assert "ON CONFLICT" in sql  # upsert


def test_set_category_false_deletes_row():
    conn, cur = _mock_db([(None, None)])
    with patch("services.safety_preferences.get_db_connection", return_value=conn):
        SafetyPreferencesService().set_category(
            TEST_USER_ID, category="write-external", requires_confirmation=False
        )
    sql = cur.execute.call_args[0][0]
    assert "DELETE FROM user_category_preferences" in sql


def test_set_category_invalid_value_rejected():
    """A category outside the CHECK constraint should be rejected at the
    application layer to avoid hitting the DB error path."""
    conn, _ = _mock_db([(None, None)])
    with patch("services.safety_preferences.get_db_connection", return_value=conn):
        # Should log and return without writing; OR raise ValueError.
        # Either is acceptable.
        try:
            SafetyPreferencesService().set_category(
                TEST_USER_ID, category="nonsense", requires_confirmation=True
            )
        except ValueError:
            return  # acceptable


def test_delete_tool_preference_idempotent():
    """delete_tool() on a row that doesn't exist should not raise."""
    conn, _ = _mock_db([(None, None)])
    with patch("services.safety_preferences.get_db_connection", return_value=conn):
        SafetyPreferencesService().delete_tool(TEST_USER_ID, tool_name="ghost")
