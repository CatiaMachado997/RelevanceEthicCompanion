"""Tests for Fernet credential encryption."""

import json
import pytest
from unittest.mock import patch
from utils.encryption import encrypt_credentials, decrypt_credentials


class TestEncryption:
    def test_round_trip(self):
        """Encrypt then decrypt returns original dict."""
        original = {"access_token": "tok_abc", "refresh_token": "ref_xyz"}
        encrypted = encrypt_credentials(original)
        assert isinstance(encrypted, str)
        assert "access_token" not in encrypted  # not plaintext
        recovered = decrypt_credentials(encrypted)
        assert recovered == original

    def test_different_calls_produce_different_ciphertext(self):
        """Fernet adds random IV — same input → different output each time."""
        data = {"key": "value"}
        assert encrypt_credentials(data) != encrypt_credentials(data)

    def test_decrypt_invalid_raises_value_error(self):
        with pytest.raises(ValueError, match="decrypt"):
            decrypt_credentials("not-valid-base64-ciphertext!!!")

    def test_encrypt_returns_string(self):
        result = encrypt_credentials({"x": 1})
        assert isinstance(result, str) and len(result) > 0
