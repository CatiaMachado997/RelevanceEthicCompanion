"""Test that get_db_connection works with a mocked pool."""
from unittest.mock import MagicMock, patch
from utils.db import get_db_connection


class TestDbPool:
    def test_uses_pool_when_available(self):
        """When pool is set, get_db_connection uses pool.connection()."""
        mock_conn = MagicMock()
        mock_pool = MagicMock()
        mock_pool.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_pool.connection.return_value.__exit__ = MagicMock(return_value=False)

        with patch("utils.db._pool", mock_pool):
            with get_db_connection() as conn:
                assert conn is mock_conn

        mock_pool.connection.assert_called_once()
