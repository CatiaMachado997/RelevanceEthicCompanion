"""Deterministic retrieval-query cleanup and rank fusion helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

_PREFIXES = (
    re.compile(r"^here is (?:a |the )?rewritten scenario[^:]*:\s*", re.IGNORECASE),
    re.compile(
        r"^based on the provided context,.*?here is the rewritten scenario:\s*",
        re.IGNORECASE | re.DOTALL,
    ),
)
_META_TAIL = re.compile(
    r"\n\s*(?:this rewritten scenario|i(?:'ve| have)? added|note\s*:|\(note\s*:).*$",
    re.IGNORECASE | re.DOTALL,
)
_ENTITY = re.compile(
    r"\b(?:AI RMF|ALTAI|LMMs?|WHO|UNESCO|NIST|GDPR|TFUE|EU AI Act|"
    r"Regulation \(EU\) \d{4}/\d+|Regulamento \(UE\) \d{4}/\d+)\b",
    re.IGNORECASE,
)
_BILINGUAL_TERMS = (
    ("artificial intelligence", "inteligência artificial"),
    ("data protection", "proteção de dados"),
    ("human rights", "direitos humanos"),
    ("risk management", "gestão de riscos"),
    ("transparency", "transparência"),
    ("explainability", "explicabilidade"),
    ("privacy", "privacidade"),
    ("governance", "governação"),
    ("governance", "governança"),
    ("safety", "segurança"),
    ("environmental", "ambiental"),
    ("fundamental rights", "direitos fundamentais"),
)
_FOLLOWUP_PREFIX = re.compile(
    r"^(?:and|also|but|so|then|what about|how about|can you|could you|please)\b",
    re.IGNORECASE,
)
_REFERENTIAL_TERM = re.compile(
    r"\b(?:it|its|that|this|those|these|they|them|same|former|latter)\b",
    re.IGNORECASE,
)


def contextualize_followup_query(query: str, history: list[dict]) -> str:
    """Add the latest user request only when a retrieval query depends on it."""
    current = re.sub(r"\s+", " ", (query or "").strip())
    if not current:
        return current

    is_followup = bool(_FOLLOWUP_PREFIX.search(current)) or (
        len(current.split()) <= 24 and bool(_REFERENTIAL_TERM.search(current))
    )
    if not is_followup:
        return current

    previous = ""
    for turn in reversed(history or []):
        if not isinstance(turn, dict) or turn.get("role") != "user":
            continue
        previous = re.sub(r"\s+", " ", str(turn.get("content") or "").strip())
        if previous:
            break
    if not previous or previous.casefold() == current.casefold():
        return current
    if len(previous) > 700:
        previous = f"{previous[:350]} … {previous[-350:]}"
    return f"Previous request: {previous}\nCurrent follow-up: {current}"


def clean_retrieval_query(query: str) -> str:
    """Remove synthetic/prompt narration while preserving the user's scenario."""
    cleaned = (query or "").strip()
    for pattern in _PREFIXES:
        cleaned = pattern.sub("", cleaned, count=1)
    cleaned = _META_TAIL.sub("", cleaned).strip(" \n:-")
    return re.sub(r"\s+", " ", cleaned)


def expand_multilingual_query(query: str) -> str:
    """Add compact bilingual domain terms while preserving named frameworks."""
    normalized = re.sub(r"\s+", " ", (query or "").strip())
    lowered = normalized.casefold()
    additions: list[str] = []
    additions.extend(match.group(0) for match in _ENTITY.finditer(normalized))
    for english, portuguese in _BILINGUAL_TERMS:
        if english in lowered:
            additions.append(portuguese)
        if portuguese in lowered:
            additions.append(english)
    unique = list(dict.fromkeys(value.casefold() for value in additions))
    return " ".join([normalized, *unique]).strip()


def build_retrieval_queries(query: str, *, expand: bool = False) -> list[str]:
    """Return a compact query first and the original as a recall-preserving fallback."""
    original = re.sub(r"\s+", " ", (query or "").strip())
    cleaned = clean_retrieval_query(original)
    expanded = expand_multilingual_query(cleaned) if expand else ""
    return list(
        dict.fromkeys(value for value in (cleaned, expanded, original) if value)
    )


def retrieval_query_weights(
    original_query: str,
    queries: list[str],
    *,
    original_weight: float,
    expansion_weight: float = 0.8,
) -> list[float]:
    """Weight cleaned, expanded, and original fallback queries deterministically."""
    original = re.sub(r"\s+", " ", (original_query or "").strip())
    cleaned = clean_retrieval_query(original)
    weights: list[float] = []
    for index, query in enumerate(queries):
        if index == 0:
            weights.append(1.0)
        elif query == original and original != cleaned:
            weights.append(original_weight)
        else:
            weights.append(expansion_weight)
    return weights


def reciprocal_rank_fusion(
    ranked_lists: Iterable[list[dict[str, Any]]],
    *,
    rank_constant: int = 60,
    weights: Iterable[float] | None = None,
) -> list[dict[str, Any]]:
    """Fuse multiple result lists by UUID without duplicating chunks."""
    by_id: dict[str, dict[str, Any]] = {}
    scores: dict[str, float] = {}
    best_hybrid: dict[str, float] = {}
    ranked_lists = list(ranked_lists)
    list_weights = list(weights) if weights is not None else [1.0] * len(ranked_lists)
    if len(list_weights) != len(ranked_lists):
        raise ValueError("RRF weights must match the number of ranked lists")
    for ranked, weight in zip(ranked_lists, list_weights):
        for rank, item in enumerate(ranked, start=1):
            key = str(item.get("uuid") or item.get("chunk_uuid") or "")
            if not key:
                continue
            by_id.setdefault(key, item)
            scores[key] = scores.get(key, 0.0) + weight / (rank_constant + rank)
            best_hybrid[key] = max(
                best_hybrid.get(key, float("-inf")),
                float(item.get("score") or 0.0),
            )

    fused: list[dict[str, Any]] = []
    for key, item in by_id.items():
        row = dict(item)
        row["hybrid_score"] = best_hybrid[key]
        row["score"] = scores[key]
        fused.append(row)
    return sorted(fused, key=lambda row: float(row["score"]), reverse=True)
