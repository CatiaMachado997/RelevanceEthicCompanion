"""Daily token budget tracker — ported from orchestrator_v2.py."""

from typing import Dict, Any, Optional
from datetime import datetime

_DAILY_TOKEN_LIMIT = 100_000
_daily_tokens: Dict[str, Dict[str, Any]] = {}


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def check_token_warning(user_id: str, new_tokens: int) -> Optional[dict]:
    """Update daily counter and return a warning event dict if a threshold is crossed."""
    today = datetime.now().strftime("%Y-%m-%d")
    entry = _daily_tokens.get(user_id)
    if not entry or entry["date"] != today:
        _daily_tokens[user_id] = {
            "date": today,
            "used": 0,
            "warned_75": False,
            "warned_85": False,
        }
        entry = _daily_tokens[user_id]
    entry["used"] += new_tokens
    used = entry["used"]
    remaining = max(0, _DAILY_TOKEN_LIMIT - used)
    pct = used / _DAILY_TOKEN_LIMIT
    if pct >= 0.85 and not entry["warned_85"]:
        entry["warned_85"] = True
        return {
            "event": "rate_limit_warning",
            "level": "high",
            "used_pct": int(pct * 100),
            "message": f"Warning: ~15% of your daily token limit remaining (~{remaining:,} tokens).",
        }
    if pct >= 0.75 and not entry["warned_75"]:
        entry["warned_75"] = True
        return {
            "event": "rate_limit_warning",
            "level": "medium",
            "used_pct": int(pct * 100),
            "message": f"~25% of your daily token limit remaining (~{remaining:,} tokens).",
        }
    return None
