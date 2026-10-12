from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Participant, ProfileAnalysis, SourceRecord
from app.schemas.dating import AgentMessageSchema  # noqa: F401 — ensure schemas load
from app.schemas.participant import AnalysisResultSchema
from app.services.evidence import validate_analysis_against_sources
from app.services.heuristics import (
    DATE_IDEAS,
    HOBBIES,
    INTERESTS,
    SIGNALS,
    content_lines,
    find_hits,
    related,
)
from app.services.llm import LLMError, LLMProvider

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Evidence-backed list fields, in the order they are persisted.
_EVIDENCE_KEYS = ("needs", "interests", "hobbies", "values", "personality_traits", "explicit_preferences")
_POST_LINE = re.compile(r'^(\d+\.\s|- ")')


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def _field(text: str, label: str) -> str:
    """Value of a ``Label: value`` line in scraped profile text."""
    prefix = f"{label}:"
    for line in (text or "").splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def _self_description(text: str) -> str:
    """Profile text minus individual posts — where people describe themselves."""
    return "\n".join(ln for ln in content_lines(text) if not _POST_LINE.match(ln))


def _posts(text: str) -> list[str]:
    return [_POST_LINE.sub("", ln).strip('" ') for ln in content_lines(text) if _POST_LINE.match(ln)]


def _avg(items: list[dict[str, Any]], default: float) -> float:
    if not items:
        return default
    return round(sum(float(i.get("confidence", 0)) for i in items) / len(items), 2)


def deterministic_analysis(
    linkedin_text: str,
    instagram_text: str,
    display_name: str = "",
) -> dict[str, Any]:
    """Evidence-grounded rule-based analysis used when no LLM is available.

    Labeled via model_name='deterministic-v2'. Every claim quotes the profile
    line that triggered it; needs are inferences from those same lines.
    """
    sources = (("linkedin", linkedin_text), ("instagram", instagram_text))
    interests: list[dict[str, Any]] = []
    hobbies: list[dict[str, Any]] = []
    prefs: list[dict[str, Any]] = []
    lifestyle: list[dict[str, Any]] = []

    # 1. Things people say about themselves outright ("passionate about ...").
    phrase_patterns = [
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
    buckets = {"interest": interests, "hobby": hobbies, "preference": prefs, "lifestyle": lifestyle}
    for source_type, text in sources:
        described = _self_description(text)
        for pattern, kind in phrase_patterns:
            for match in re.finditer(pattern, described, flags=re.IGNORECASE):
                buckets[kind].append(
                    {
                        "value": match.group(1).strip(" .,:;")[:120],
                        "evidence": match.group(0).strip()[:240],
                        "source_type": source_type,
                        "confidence": 0.6,
                    }
                )

    # 2. Hobbies and interests evidenced by what they post and list.
    for table, bucket in ((HOBBIES, hobbies), (INTERESTS, interests)):
        found: list[dict[str, Any]] = []
        for label, keywords in table.items():
            best: tuple[int, str, str] | None = None
            for source_type, text in sources:
                count, evidence = find_hits(text, keywords)
                if count and (best is None or count > best[0]):
                    best = (count, evidence, source_type)
            if best and not any(related(label, existing["value"]) for existing in bucket):
                found.append(
                    {
                        "value": label,
                        "evidence": best[1],
                        "source_type": best[2],
                        "confidence": round(min(0.85, 0.4 + 0.1 * best[0]), 2),
                    }
                )
        found.sort(key=lambda item: -item["confidence"])
        bucket.extend(found)

    # Hashtags they chose themselves are topics they care about.
    tagged = 0
    for source_type, text in sources:
        for tag in dict.fromkeys(re.findall(r"#(\w{3,30})", text)):
            label = tag.replace("_", " ")
            known = hobbies + interests
            if tagged < 3 and not any(related(label, existing["value"]) for existing in known):
                tagged += 1
                interests.append(
                    {
                        "value": label,
                        "evidence": f"#{tag}",
                        "source_type": source_type,
                        "confidence": 0.45,
                    }
                )

    # 3. Personality, values and needs inferred from recurring signals.
    signals: list[tuple[int, Any, str, str]] = []
    for signal in SIGNALS:
        hits = [(find_hits(text, signal.keywords), source_type) for source_type, text in sources]
        total = sum(h[0][0] for h in hits)
        if total:
            (_, evidence), source_type = max(hits, key=lambda h: h[0][0])
            signals.append((total, signal, evidence, source_type))
    signals.sort(key=lambda s: -s[0])

    traits: list[dict[str, Any]] = []
    values: list[dict[str, Any]] = []
    needs: list[dict[str, Any]] = []
    for total, signal, evidence, source_type in signals:
        confidence = round(min(0.8, 0.35 + 0.08 * total), 2)
        base = {"evidence": evidence, "source_type": source_type, "key": signal.key}
        traits.append({**base, "value": signal.trait, "confidence": confidence})
        values.append({**base, "value": signal.value, "confidence": round(confidence - 0.05, 2)})
        needs.append(
            {
                **base,
                "value": signal.need,
                "confidence": round(confidence - 0.1, 2),
                "why": f"Inferred from repeated signs they are {signal.trait.lower()}.",
            }
        )
    # Stated wants are the strongest needs there are.
    for pref in prefs:
        needs.insert(
            0,
            {**pref, "confidence": 0.7, "why": "Stated directly on their profile."},
        )

    # 4. Lifestyle and communication style.
    location = _field(linkedin_text, "Location")
    headline = _field(linkedin_text, "Headline")
    if location:
        lifestyle.append(
            {"value": f"Based in {location}", "evidence": location, "source_type": "linkedin", "confidence": 0.75}
        )
    if headline:
        lifestyle.append(
            {"value": f"Works as {headline}", "evidence": headline, "source_type": "linkedin", "confidence": 0.75}
        )
    communication: list[dict[str, Any]] = []
    captions = _posts(instagram_text)
    if captions:
        average = sum(len(c) for c in captions) / len(captions)
        style = (
            "Writes long, story-driven Instagram captions"
            if average > 280
            else "Keeps Instagram captions short and visual"
        )
        communication.append(
            {"value": style, "evidence": captions[0][:170], "source_type": "instagram", "confidence": 0.55}
        )
    linkedin_posts = _posts(linkedin_text)
    if linkedin_posts:
        communication.append(
            {
                "value": "Shares opinions and ideas publicly on LinkedIn",
                "evidence": linkedin_posts[0][:170],
                "source_type": "linkedin",
                "confidence": 0.6,
            }
        )

    # 5. Narrative pieces.
    name = display_name or _field(linkedin_text, "Name") or _field(instagram_text, "Name")
    about = _field(linkedin_text, "About")
    bio = _field(instagram_text, "Bio")
    top_hobbies = [h["value"] for h in hobbies[:3]]
    top_interests = [i["value"] for i in interests[:3]]

    summary_parts: list[str] = []
    if name and headline:
        summary_parts.append(f"{name} — {headline}.")
    elif name:
        summary_parts.append(f"{name}.")
    if location:
        summary_parts.append(f"Based in {location}.")
    if about:
        summary_parts.append(f"In their own words on LinkedIn: “{about[:220]}”")
    if bio:
        summary_parts.append(f"Instagram bio: “{bio[:160]}”")
    if top_hobbies:
        summary_parts.append("Outside work, their posts point to " + ", ".join(top_hobbies).lower() + ".")
    if top_interests:
        summary_parts.append("They keep returning to " + ", ".join(top_interests).lower() + ".")
    if not summary_parts:
        if linkedin_text.strip():
            summary_parts.append("Professional signals drawn from LinkedIn text.")
        if instagram_text.strip():
            summary_parts.append("Lifestyle signals drawn from Instagram text.")
        if not summary_parts:
            summary_parts.append("Insufficient content for a substantive profile summary.")

    idea = next((DATE_IDEAS[h["value"]] for h in hobbies if h["value"] in DATE_IDEAS), "")
    ideal_date = (
        f"{idea[0].upper()}{idea[1:]}."
        if idea
        else "A relaxed first conversation over coffee — too little is public to be more specific."
    )

    raw = {
        "headline": headline or bio[:140] or ", ".join(top_hobbies + top_interests)[:140],
        "summary": " ".join(summary_parts),
        "needs": needs[:6],
        "interests": interests[:10],
        "hobbies": hobbies[:10],
        "values": values[:5],
        "personality_traits": traits[:6],
        "explicit_preferences": prefs[:8],
        "communication_clues": communication,
        "lifestyle_clues": lifestyle[:8],
        "relationship_preferences": [
            p for p in prefs if "relationship" in p["value"].lower() or "partner" in p["value"].lower()
        ],
        "ideal_date": ideal_date,
        "contradictions": [],
        "uncertainties": [
            "Rule-based analyzer used (no LLM configured); claims come from keyword evidence and stay conservative.",
            "Needs are inferences from public behaviour, not statements made by the person.",
            "Sensitive traits are never inferred.",
        ],
        "missing_information": [
            "Relationship goals are not stated on either profile"
            if not prefs
            else "More detail on what they want would sharpen the ranking",
            "Daily rhythm outside of work is unknown",
            "Life stage and availability are not confirmed publicly",
        ],
        "source_coverage": {},
    }
    result = validate_analysis_against_sources(raw, linkedin_text, instagram_text)
    result["confidence_by_attribute"] = {
        "summary": 0.55 if (linkedin_text.strip() and instagram_text.strip()) else 0.35 if (linkedin_text.strip() or instagram_text.strip()) else 0.1,
        "needs": _avg(result["needs"], 0.1),
        "hobbies": _avg(result["hobbies"], 0.15),
        "interests": _avg(result["interests"], 0.15),
        "personality": _avg(result["personality_traits"], 0.1),
    }
    return result


async def analyze_participant(
    db: Session,
    participant_id: int,
    *,
    allow_deterministic_fallback: bool = True,
) -> ProfileAnalysis:
    settings = get_settings()
    participant = db.get(Participant, participant_id)
    display_name = participant.display_name if participant else ""
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
            "Neither profile could be read, so there is nothing to analyze. "
            "Check that both links are public, or paste the profile text."
        )

    llm = LLMProvider()
    model_name = "deterministic-v2"
    status = "completed"
    result_dict: dict[str, Any]

    if llm.configured:
        system = _load_prompt("analysis_v2.txt")
        user = (
            f"The person: {display_name or 'name not given'}\n\n"
            f"=== SOURCE 1: LINKEDIN (public profile) ===\n{linkedin_text[:12000] or '(could not be read)'}\n\n"
            f"=== SOURCE 2: INSTAGRAM (public profile) ===\n{instagram_text[:12000] or '(could not be read)'}\n"
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
            result_dict = deterministic_analysis(linkedin_text, instagram_text, display_name)
            model_name = "deterministic-v2-after-llm-failure"
            status = "completed_with_fallback"
    else:
        if not allow_deterministic_fallback:
            raise LLMError("LLM not configured")
        result_dict = deterministic_analysis(linkedin_text, instagram_text, display_name)

    analysis = ProfileAnalysis(
        participant_id=participant_id,
        headline=(result_dict.get("headline") or "")[:400],
        summary=result_dict.get("summary", ""),
        needs=result_dict.get("needs", []),
        interests=result_dict.get("interests", []),
        hobbies=result_dict.get("hobbies", []),
        core_values=result_dict.get("values", []),
        personality_traits=result_dict.get("personality_traits", []),
        explicitly_stated_preferences=result_dict.get("explicit_preferences", []),
        communication_clues=result_dict.get("communication_clues", []),
        lifestyle_clues=result_dict.get("lifestyle_clues", []),
        relationship_preferences=result_dict.get("relationship_preferences", []),
        ideal_date=result_dict.get("ideal_date", ""),
        evidence_items=[
            item for key in _EVIDENCE_KEYS for item in result_dict.get(key, [])
        ],
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
        .order_by(ProfileAnalysis.created_at.desc(), ProfileAnalysis.id.desc())
        .first()
    )


def public_analysis_view(analysis: ProfileAnalysis) -> dict[str, Any]:
    """Everything an agent knows about its own person."""
    return {
        "headline": analysis.headline or "",
        "summary": analysis.summary,
        "needs": analysis.needs or [],
        "interests": analysis.interests,
        "hobbies": analysis.hobbies,
        "core_values": analysis.core_values or [],
        "personality_traits": analysis.personality_traits or [],
        "explicitly_stated_preferences": analysis.explicitly_stated_preferences,
        "communication_clues": analysis.communication_clues,
        "lifestyle_clues": analysis.lifestyle_clues,
        "relationship_preferences": analysis.relationship_preferences,
        "ideal_date": analysis.ideal_date or "",
        "uncertainty_notes": analysis.uncertainty_notes,
        "missing_information": analysis.missing_information,
    }
