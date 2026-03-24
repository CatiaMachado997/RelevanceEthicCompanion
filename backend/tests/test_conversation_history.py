import pytest
from unittest.mock import patch, MagicMock
from services.context_manager import ContextManager


@patch('services.context_manager.get_db_connection')
def test_store_conversation_turn(mock_db):
    mock_conn = MagicMock()
    mock_db.return_value.__enter__.return_value = mock_conn
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur

    cm = ContextManager()
    cm.store_conversation_turn(
        user_id='00000000-0000-0000-0000-000000000000',
        role='user',
        content='Hello'
    )

    mock_cur.execute.assert_called_once()
    call_args = mock_cur.execute.call_args[0]
    assert 'INSERT INTO conversation_turns' in call_args[0]


@patch('services.context_manager.get_db_connection')
def test_get_conversation_history_returns_ordered(mock_db):
    mock_conn = MagicMock()
    mock_db.return_value.__enter__.return_value = mock_conn
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_cur.fetchall.return_value = [
        {'role': 'user', 'content': 'Hi'},
        {'role': 'assistant', 'content': 'Hello! How can I help?'},
    ]

    cm = ContextManager()
    turns = cm.get_conversation_history(
        user_id='00000000-0000-0000-0000-000000000000',
        limit=20
    )

    assert len(turns) == 2
    assert turns[0]['role'] == 'user'
    assert turns[1]['role'] == 'assistant'
