"""
Rate limiting configuration.

Uses slowapi (wraps `limits` library). The limiter is registered in main.py.

Two key functions:
- `get_remote_address` (from slowapi) — used for IP-based limits (auth endpoints)
- `get_user_id_or_ip` — used for user-based limits (authenticated tool endpoints)
"""
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def get_user_id_or_ip(request: Request) -> str:
    """Key function: use user_id from request state, fall back to IP."""
    try:
        user_id = request.state.user_id
        if user_id:
            return str(user_id)
    except AttributeError:
        pass
    return get_remote_address(request)


# Global limiter: 200 req/min default (applies to all routes without a decorator)
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
