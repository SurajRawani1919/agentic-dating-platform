"""Validate that analysis claims cite evidence present in source material."""

from __future__ import annotations

from typing import Any


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split())


def evidence_supported(excerpt: str, source_text: str, min_overlap_tokens: int = 2) -> bool:
    excerpt_n = _normalize(excerpt)
    source_n = _normalize(source_text)
    if not excerpt_n or not source_n:
        return False
    if excerpt_n in source_n:
        return True
    tokens = [t for t in excerpt_n.split() if len(t) > 3]
    if not tokens:
        return False
    hits = sum(1 for t in tokens if t in source_n)
    return hits >= min(min_overlap_tokens, len(tokens))


def filter_grounded_items(
    items: list[dict[str, Any]],
    linkedin_text: str,
    instagram_text: str,
) -> list[dict[str, Any]]:
    grounded: list[dict[str, Any]] = []
    for item in items:
        source_type = item.get("source_type")
        evidence = str(item.get("evidence", ""))
        source = linkedin_text if source_type == "linkedin" else instagram_text
        if evidence_supported(evidence, source):
            grounded.append(item)
        else:
            # Keep claim only as uncertainty annotation — do not present as fact
            continue
    return grounded


def validate_analysis_against_sources(
    analysis: dict[str, Any],
    linkedin_text: str,
    instagram_text: str,
) -> dict[str, Any]:
    result = dict(analysis)
    for key in (
        "interests",
        "hobbies",
        "explicit_preferences",
        "communication_clues",
        "lifestyle_clues",
        "relationship_preferences",
    ):
        items = result.get(key) or []
        if isinstance(items, list):
            dict_items = [i if isinstance(i, dict) else {"value": str(i), "evidence": "", "source_type": "linkedin", "confidence": 0.3} for i in items]
            result[key] = filter_grounded_items(dict_items, linkedin_text, instagram_text)

    uncertainties = list(result.get("uncertainties") or [])
    if not linkedin_text.strip():
        uncertainties.append("LinkedIn content missing; LinkedIn-derived claims omitted.")
    if not instagram_text.strip():
        uncertainties.append("Instagram content missing; Instagram-derived claims omitted.")
    result["uncertainties"] = uncertainties
    result["source_coverage"] = {
        "linkedin": bool(linkedin_text.strip()),
        "instagram": bool(instagram_text.strip()),
        "notes": "Claims without matching evidence excerpts were removed.",
    }
    return result
