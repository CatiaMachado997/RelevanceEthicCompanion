"""Deterministic local rollout assignments with no external flag service."""

from __future__ import annotations

import hashlib
import os
from typing import Any


def rollout_variant(flag: str, user_id: str, *, percent_env: str) -> str:
    forced = os.getenv(f"{flag.upper()}_FORCE_VARIANT", "").lower()
    if forced in {"control", "treatment"}:
        return forced
    percent = max(0, min(100, int(os.getenv(percent_env, "0"))))
    bucket = (
        int.from_bytes(hashlib.sha256(f"{flag}:{user_id}".encode()).digest()[:4], "big")
        % 100
    )
    return "treatment" if bucket < percent else "control"


def rag_rollout_config(user_id: str) -> dict[str, Any]:
    variant = rollout_variant("RAG_ROLLOUT", user_id, percent_env="RAG_ROLLOUT_PERCENT")
    return {
        "variant": variant,
        "alpha": float(os.getenv("RAG_ROLLOUT_ALPHA", "0.5")),
        "top_k": int(os.getenv("RAG_ROLLOUT_TOP_K", "4")),
        "query_expansion": os.getenv("RAG_ROLLOUT_QUERY_EXPANSION", "0") == "1",
    }
