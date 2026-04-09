"""
Fernet symmetric encryption for credential storage.

Credentials in user_tool_connections.credentials are encrypted at rest.
Without ENCRYPTION_KEY, an ephemeral key is used (credentials lost on restart).

Usage:
    from utils.encryption import encrypt_credentials, decrypt_credentials

    stored = encrypt_credentials({"access_token": "tok_abc"})
    recovered = decrypt_credentials(stored)
"""
from __future__ import annotations

import json
import logging
import threading

from cryptography.fernet import Fernet, InvalidToken

from config import settings

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None
_fernet_lock = threading.Lock()


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        with _fernet_lock:
            if _fernet is None:
                key = settings.ENCRYPTION_KEY
                if not key:
                    logger.warning(
                        "ENCRYPTION_KEY not set — using ephemeral key. "
                        "Credentials will not survive restarts. Set ENCRYPTION_KEY in .env."
                    )
                    key = Fernet.generate_key().decode()
                _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_credentials(credentials: dict) -> str:
    """Encrypt a credentials dict to a Fernet token string (URL-safe base64)."""
    plaintext = json.dumps(credentials).encode()
    return _get_fernet().encrypt(plaintext).decode()


def decrypt_credentials(encrypted: str) -> dict:
    """Decrypt a Fernet token string back to the credentials dict.

    Raises:
        ValueError: If the token is invalid or from a different key.
    """
    try:
        plaintext = _get_fernet().decrypt(encrypted.encode())
        return json.loads(plaintext)
    except (InvalidToken, Exception) as exc:
        raise ValueError(f"Failed to decrypt credentials: {exc}") from exc
