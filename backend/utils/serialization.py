"""
Serialization utilities for converting database objects to JSON
"""
from typing import Any, Dict
from datetime import datetime
from uuid import UUID


def serialize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert a database row to a JSON-serializable dictionary.

    Handles:
    - UUID objects -> strings
    - datetime objects -> ISO format strings
    - Other types pass through

    Args:
        row: Dictionary from database query

    Returns:
        JSON-serializable dictionary
    """
    if not row:
        return {}

    serialized = {}
    for key, value in row.items():
        if isinstance(value, UUID):
            serialized[key] = str(value)
        elif isinstance(value, datetime):
            serialized[key] = value.isoformat()
        else:
            serialized[key] = value

    return serialized


def serialize_rows(rows: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """
    Convert a list of database rows to JSON-serializable dictionaries.

    Args:
        rows: List of dictionaries from database query

    Returns:
        List of JSON-serializable dictionaries
    """
    return [serialize_row(row) for row in rows]
