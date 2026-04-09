"""Tests that supabase_auth correctly requires ES256 tokens."""
import time

import pytest
from jose import jwk, jwt

SUPABASE_ISSUER = "https://test.supabase.co/auth/v1"
AUDIENCE = "authenticated"


@pytest.fixture
def ec_keypair():
    """Generate a fresh P-256 key pair for each test."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
    )

    priv_obj = ec.generate_private_key(ec.SECP256R1(), default_backend())
    priv_pem = priv_obj.private_bytes(
        Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()
    ).decode()
    jose_key = jwk.construct(priv_pem, algorithm="ES256")
    pub_dict = jose_key.public_key().to_dict()
    pub_dict["kid"] = "test-kid-1"
    return priv_pem, pub_dict


def _make_es256_token(private_pem: str, sub: str = "user-abc-123") -> str:
    return jwt.encode(
        {
            "sub": sub,
            "aud": AUDIENCE,
            "iss": SUPABASE_ISSUER,
            "exp": int(time.time()) + 3600,
        },
        private_pem,
        algorithm="ES256",
        headers={"kid": "test-kid-1"},
    )


def test_es256_token_decoded_successfully(ec_keypair, monkeypatch):
    """_decode_supabase_token accepts a valid ES256 token."""
    priv_pem, pub_jwk = ec_keypair
    import utils.supabase_auth as auth_mod

    monkeypatch.setattr(auth_mod, "_fetch_jwks", lambda: {"keys": [pub_jwk]})
    monkeypatch.setattr(auth_mod, "_build_issuer", lambda: SUPABASE_ISSUER)
    monkeypatch.setattr(auth_mod.settings, "SUPABASE_JWT_AUDIENCE", AUDIENCE)

    token = _make_es256_token(priv_pem)
    claims = auth_mod._decode_supabase_token(token)
    assert claims["sub"] == "user-abc-123"


def test_rs256_token_rejected(ec_keypair, monkeypatch):
    """_decode_supabase_token rejects an RS256-signed token (wrong algorithm)."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
    )

    _, pub_jwk = ec_keypair
    import utils.supabase_auth as auth_mod

    monkeypatch.setattr(auth_mod, "_fetch_jwks", lambda: {"keys": [pub_jwk]})
    monkeypatch.setattr(auth_mod, "_build_issuer", lambda: SUPABASE_ISSUER)
    monkeypatch.setattr(auth_mod.settings, "SUPABASE_JWT_AUDIENCE", AUDIENCE)

    rsa_key = rsa.generate_private_key(65537, 2048, default_backend())
    rsa_pem = rsa_key.private_bytes(
        Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()
    ).decode()
    rs256_token = jwt.encode(
        {"sub": "evil", "aud": AUDIENCE, "iss": SUPABASE_ISSUER, "exp": int(time.time()) + 3600},
        rsa_pem,
        algorithm="RS256",
    )

    from jose import JWTError
    with pytest.raises((JWTError, Exception)) as exc_info:
        auth_mod._decode_supabase_token(rs256_token)
    # Must be a JWT-related error, not a programming error
    assert isinstance(exc_info.value, (JWTError, ValueError))


def test_dev_fallback_disabled_when_enforcement_enabled(monkeypatch):
    """With AUTH_ENFORCEMENT_ENABLED=True, _is_dev_fallback_enabled() returns False."""
    import utils.supabase_auth as auth_mod
    monkeypatch.setattr(auth_mod.settings, "AUTH_ENFORCEMENT_ENABLED", True)
    monkeypatch.setattr(auth_mod.settings, "ENVIRONMENT", "production")

    # _is_dev_fallback_enabled() must return False
    assert auth_mod._is_dev_fallback_enabled() is False
