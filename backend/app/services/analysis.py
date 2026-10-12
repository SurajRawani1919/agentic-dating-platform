from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ProfileAnalysis, SourceRecord
from app.schemas.dating import AgentMessageSchema  # noqa: F401 — ensure schemas load
from app.schemas.participant import AnalysisResultSchema
from app.services.evidence import validate_analysis_against_sources
from app.services.llm import LLMError, LLMProvider

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def _extract_keywords(text: str) -> list[str]:
    stop = {
        "with", "from", "that", "this", "have", "been", "were", "their", "about",
        "into", "over", "under", "after", "before", "and", "the", "for", "you",
    }
    words = re.findall(r"[A-Za-z][A-Za-z\-']{3,}", text.lower())
    seen: list[str] = []
    for w in words:
        if w in stop or w in seen:
            continue
        seen.append(w)
        if len(seen) >= 40:
            break
    return seen


def deterministic_analysis(
    linkedin_text: str,
    instagram_text: str,
) -> dict[str, Any]:
    """Evidence-grounded heuristic analysis used when LLM is unavailable.

    Clearly labeled via model_name='deterministic-v1'. Not fabricated live AI.
    """
    interests: list[dict[str, Any]] = []
    hobbies: list[dict[str, Any]] = []
    prefs: list[dict[str, Any]] = []
    lifestyle: list[dict[str, Any]] = []

    interest_patterns = [
        (r"interested in ([^.!\n]{3,60})", "interest"),
        (r"passionate about ([^.!\n]{3,60})", "interest"),
        (r"love[s]? ([^.!\n]{3,40})", "hobby"),
        (r"enjoy[s]? ([^.!\n]{3,40})", "hobby"),
        (r"hobby[:\s]+([^.!\n]{3,60})", "hobby"),
        (r"looking for ([^.!\n]{3,60})", "preference"),
        (r"prefer[s]? ([^.!\n]{3,60})", "preference"),
        (r"lives? in ([^.!\n]{3,40})", "lifestyle"),
        (r"based in ([^.!\n]{3,40})", "lifestyle"),
    ]

    for source_type, text in (("linkedin", linkedin_text), ("instagram", instagram_text)):
        if not text.strip():
            continue
        for pattern, kind in interest_patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                value = match.group(1).strip(" .,:;")
                evidence = match.group(0).strip()
                item = {
                    "value": value[:120],
                    "evidence": evidence[:240],
                    "source_type": source_type,
                    "confidence": 0.55,
                }
                if kind == "interest":
                    interests.append(item)
                elif kind == "hobby":
                    hobbies.append(item)
                elif kind == "preference":
                    prefs.append(item)
                else:
                    lifestyle.append(item)

    # Fallback keyword interests from hashtags / role words
    for source_type, text in (("linkedin", linkedin_text), ("instagram", instagram_text)):
        for tag in re.findall(r"#(\w{3,30})", text):
            hobbies.append(
                {
                    "value": tag.replace("_", " "),
                    "evidence": f"#{tag}",
                    "source_type": source_type,
                    "confidence": 0.45,
                }
            )

    summary_parts = []
    if linkedin_text.strip():
        summary_parts.append("Professional signals drawn from authorized LinkedIn text.")
    if instagram_text.strip():
        summary_parts.append("Lifestyle signals drawn from authorized Instagram text.")
    if not summary_parts:
        summary_parts.append("Insufficient permitted content for a substantive profile summary.")

    top_interests = [i["value"] for i in interests[:3]]
    if top_interests:
        summary_parts.append("Notable interests include: " + ", ".join(top_interests) + ".")

    raw = {
        "summary": " ".join(summary_parts),
        "interests": interests[:12],
        "hobbies": hobbies[:12],
        "explicit_preferences": prefs[:8],
        "communication_clues": [],
        "lifestyle_clues": lifestyle[:8],
        "relationship_preferences": [p for p in prefs if "relationship" in p["value"].lower() or "partner" in p["value"].lower()],
        "contradictions": [],
        "uncertainties": [
            "Deterministic analyzer used; confidence is moderate and evidence-limited.",
            "Sensitive traits are never inferred.",
        ],
        "missing_information": [
            "Relationship goals not explicitly stated" if not prefs else "Additional preference detail would improve ranking confidence",
            "Daily lifestyle rhythm unknown",
        ],
        "confidence_by_attribute": {
            "summary": 0.5 if (linkedin_text or instagram_text) else 0.1,
            "interests": 0.55 if interests else 0.15,
            "hobbies": 0.5 if hobbies else 0.15,
            "preferences": 0.45 if prefs else 0.1,
        },
        "source_coverage": {
            "linkedin": bool(linkedin_text.strip()),
            "instagram": bool(instagram_text.strip()),
            "notes": "deterministic extraction",
        },
    }
    return validate_analysis_against_sources(raw, linkedin_text, instagram_text)


async def analyze_participant(
    db: Session,
    participant_id: int,
    *,
    allow_deterministic_fallback: bool = True,
) -> ProfileAnalysis:
    settings = get_settings()
    sources = (
        db.query(SourceRecord)
        .filter(SourceRecord.participant_id == participant_id)
        .all()
    )
    linkedin = next((s for s in sources if s.source_type == "linkedin"), None)
    instagram = next((s for s in sources if s.source_type == "instagram"), None)
    linkedin_text = linkedin.permitted_content if linkedin else ""
    instagram_text = instagram.permitted_content if instagram else ""

    if not linkedin_text.strip() and not instagram_text.strip():
        raise ValueError(
            "No permitted content available. Provide authorized LinkedIn/Instagram text."
        )

    llm = LLMProvider()
    model_name = "deterministic-v1"
    status = "completed"
    result_dict: dict[str, Any]

    if llm.configured:
        system = _load_prompt("analysis_v1.txt")
        user = (
            "Analyze this participant.\n\n"
            f"LINKEDIN CONTENT:\n{linkedin_text[:12000]}\n\n"
            f"INSTAGRAM CONTENT:\n{instagram_text[:12000]}\n"
        )
        try:
            validated, model_name = await llm.complete_json(
                system_prompt=system,
                user_prompt=user,
                schema_model=AnalysisResultSchema,
            )
            result_dict = validate_analysis_against_sources(
                validated.model_dump(), linkedin_text, instagram_text
            )
        except LLMError:
            if not allow_deterministic_fallback:
                raise
            # Honest fallback — not presented as live LLM output
            result_dict = deterministic_analysis(linkedin_text, instagram_text)
            model_name = "deterministic-v1-after-llm-failure"
            status = "completed_with_fallback"
    else:
        if not allow_deterministic_fallback:
            raise LLMError("LLM not configured")
        result_dict = deterministic_analysis(linkedin_text, instagram_text)
        model_name = "deterministic-v1"

    analysis = ProfileAnalysis(
        participant_id=participant_id,
        summary=result_dict.get("summary", ""),
        interests=result_dict.get("interests", []),
        hobbies=result_dict.get("hobbies", []),
        explicitly_stated_preferences=result_dict.get("explicit_preferences", []),
        communication_clues=result_dict.get("communication_clues", []),
        lifestyle_clues=result_dict.get("lifestyle_clues", []),
        relationship_preferences=result_dict.get("relationship_preferences", []),
        evidence_items=(
            list(result_dict.get("interests", []))
            + list(result_dict.get("hobbies", []))
            + list(result_dict.get("explicit_preferences", []))
        ),
        uncertainty_notes=result_dict.get("uncertainties", []),
        confidence_by_attribute=result_dict.get("confidence_by_attribute", {}),
        source_coverage=result_dict.get("source_coverage", {}),
        contradictions=result_dict.get("contradictions", []),
        missing_information=result_dict.get("missing_information", []),
        model_name=model_name,
        prompt_version=settings.analysis_prompt_version,
        status=status,
        is_demo=False,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


def latest_analysis(db: Session, participant_id: int) -> ProfileAnalysis | None:
    return (
        db.query(ProfileAnalysis)
        .filter(ProfileAnalysis.participant_id == participant_id)
        .order_by(ProfileAnalysis.created_at.desc())
        .first()
    )


def public_analysis_view(analysis: ProfileAnalysis) -> dict[str, Any]:
    """Information an agent may know about its own person (not hidden notes)."""
    return {
        "summary": analysis.summary,
        "interests": analysis.interests,
        "hobbies": analysis.hobbies,
        "explicitly_stated_preferences": analysis.explicitly_stated_preferences,
        "lifestyle_clues": analysis.lifestyle_clues,
        "relationship_preferences": analysis.relationship_preferences,
        "uncertainty_notes": analysis.uncertainty_notes,
        "missing_information": analysis.missing_information,
    }
