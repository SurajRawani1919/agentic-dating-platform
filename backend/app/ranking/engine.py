from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import DateSession, Participant, Ranking
from app.services.analysis import latest_analysis, public_analysis_view

# Initial engineering weights — not scientifically validated.
WEIGHTS = {
    "shared_interests": 0.30,
    "preference_alignment": 0.30,
    "conversation_quality": 0.25,
    "lifestyle_compatibility": 0.15,
}


def _labels(items: list[Any]) -> set[str]:
    out: set[str] = set()
    for item in items or []:
        if isinstance(item, dict):
            val = str(item.get("value", "")).strip().lower()
        else:
            val = str(item).strip().lower()
        if val:
            out.add(val)
    return out


def _overlap_score(a: set[str], b: set[str]) -> tuple[float, list[str], float]:
    if not a and not b:
        return 0.0, [], 0.15
    if not a or not b:
        return 10.0, [], 0.25
    shared = sorted(a & b)
    union = a | b
    ratio = len(shared) / max(len(union), 1)
    score = min(100.0, 20.0 + ratio * 80.0)
    confidence = min(1.0, 0.3 + 0.1 * len(shared) + 0.05 * min(len(a), len(b)))
    return score, shared, confidence


def compute_session_scores(
    *,
    analysis_a: dict[str, Any],
    analysis_b: dict[str, Any],
    eval_a: dict[str, Any],
    eval_b: dict[str, Any],
    transcript: list[dict[str, Any]],
) -> dict[str, Any]:
    interests_a = _labels(analysis_a.get("interests")) | _labels(analysis_a.get("hobbies"))
    interests_b = _labels(analysis_b.get("interests")) | _labels(analysis_b.get("hobbies"))
    prefs_a = _labels(analysis_a.get("explicitly_stated_preferences")) | _labels(
        analysis_a.get("relationship_preferences")
    )
    prefs_b = _labels(analysis_b.get("explicitly_stated_preferences")) | _labels(
        analysis_b.get("relationship_preferences")
    )
    life_a = _labels(analysis_a.get("lifestyle_clues"))
    life_b = _labels(analysis_b.get("lifestyle_clues"))

    shared_score, shared, shared_conf = _overlap_score(interests_a, interests_b)
    pref_score, pref_shared, pref_conf = _overlap_score(prefs_a, prefs_b)
    life_score, life_shared, life_conf = _overlap_score(life_a, life_b)

    # Reciprocal conversation quality from both agent estimates + turn depth
    est_a = float(eval_a.get("compatibility_estimate") or 0)
    est_b = float(eval_b.get("compatibility_estimate") or 0)
    conf_a = float(eval_a.get("confidence") or 0)
    conf_b = float(eval_b.get("confidence") or 0)
    depth_bonus = min(20.0, len(transcript) * 2.5)
    convo_score = min(100.0, (est_a + est_b) / 2.0 * 0.8 + depth_bonus)
    convo_conf = (conf_a + conf_b) / 2.0

    insufficient: list[str] = []
    if not interests_a or not interests_b:
        insufficient.append("Interest evidence thin on one or both sides")
        shared_conf = min(shared_conf, 0.35)
    if not prefs_a or not prefs_b:
        insufficient.append("Explicit preference alignment largely unknown")
        pref_score = min(pref_score, 35.0)
        pref_conf = min(pref_conf, 0.3)
    if not life_a or not life_b:
        insufficient.append("Lifestyle compatibility insufficiently evidenced")
        life_conf = min(life_conf, 0.3)

    breakdown = {
        "shared_interests": {
            "score": round(shared_score, 2),
            "weight": WEIGHTS["shared_interests"],
            "evidence": shared[:8],
            "uncertainty": round(1 - shared_conf, 2),
            "insufficient_reason": insufficient[0] if (not interests_a or not interests_b) and insufficient else None,
        },
        "preference_alignment": {
            "score": round(pref_score, 2),
            "weight": WEIGHTS["preference_alignment"],
            "evidence": pref_shared[:8],
            "uncertainty": round(1 - pref_conf, 2),
            "insufficient_reason": "Missing explicit preferences" if not prefs_a or not prefs_b else None,
        },
        "conversation_quality": {
            "score": round(convo_score, 2),
            "weight": WEIGHTS["conversation_quality"],
            "evidence": [
                f"Agent A estimate {est_a}",
                f"Agent B estimate {est_b}",
                f"{len(transcript)} turns",
            ],
            "uncertainty": round(1 - convo_conf, 2),
            "insufficient_reason": None if transcript else "No transcript",
        },
        "lifestyle_compatibility": {
            "score": round(life_score, 2),
            "weight": WEIGHTS["lifestyle_compatibility"],
            "evidence": life_shared[:8],
            "uncertainty": round(1 - life_conf, 2),
            "insufficient_reason": "Lifestyle clues missing" if not life_a or not life_b else None,
        },
    }

    total = sum(breakdown[k]["score"] * breakdown[k]["weight"] for k in WEIGHTS)
    confidence = (
        shared_conf * WEIGHTS["shared_interests"]
        + pref_conf * WEIGHTS["preference_alignment"]
        + convo_conf * WEIGHTS["conversation_quality"]
        + life_conf * WEIGHTS["lifestyle_compatibility"]
    )

    friction = list(
        dict.fromkeys(
            list(eval_a.get("potential_friction") or [])
            + list(eval_b.get("potential_friction") or [])
        )
    )
    unanswered = list(
        dict.fromkeys(
            list(eval_a.get("unanswered_questions") or [])
            + list(eval_b.get("unanswered_questions") or [])
            + insufficient
        )
    )

    summary = (
        f"Compatibility {total:.1f}/100 with confidence {confidence:.2f}. "
        + (
            f"Shared interests: {', '.join(shared[:3])}."
            if shared
            else "Limited confirmed shared interests."
        )
    )

    return {
        "compatibility_score": round(total, 2),
        "confidence": round(min(1.0, confidence), 3),
        "score_breakdown": breakdown,
        "shared_interests": shared[:12],
        "potential_friction": friction[:12],
        "unanswered_questions": unanswered[:12],
        "date_summary": summary,
        "positive_evidence": shared[:8] + pref_shared[:4],
    }


def aggregate_rankings(db: Session, run_id: int) -> list[Ranking]:
    """Build personalized rankings from persisted sessions for a run."""
    db.query(Ranking).filter(Ranking.run_id == run_id).delete()
    sessions = (
        db.query(DateSession)
        .filter(DateSession.run_id == run_id, DateSession.status == "completed")
        .all()
    )
    participant_ids = set()
    for s in sessions:
        participant_ids.add(s.participant_a_id)
        participant_ids.add(s.participant_b_id)

    # Map unordered pair -> session
    pair_map: dict[tuple[int, int], DateSession] = {}
    for s in sessions:
        pair_map[(s.participant_a_id, s.participant_b_id)] = s

    created: list[Ranking] = []
    for pid in sorted(participant_ids):
        candidates: list[tuple[float, float, int, DateSession]] = []
        for other in sorted(participant_ids):
            if other == pid:
                continue
            key = (pid, other) if pid < other else (other, pid)
            sess = pair_map.get(key)
            if not sess or sess.compatibility_score is None:
                continue
            candidates.append(
                (
                    float(sess.compatibility_score),
                    float(sess.confidence or 0),
                    other,
                    sess,
                )
            )
        # Deterministic sort: score desc, confidence desc, candidate id asc
        candidates.sort(key=lambda x: (-x[0], -x[1], x[2]))
        for rank_i, (score, conf, cand_id, sess) in enumerate(candidates, start=1):
            row = Ranking(
                run_id=run_id,
                participant_id=pid,
                candidate_id=cand_id,
                rank=rank_i,
                compatibility_score=score,
                confidence=conf,
                score_breakdown=sess.score_breakdown or {},
                positive_evidence=sess.shared_interests or [],
                potential_mismatches=sess.potential_friction or [],
                unanswered_questions=sess.unanswered_questions or [],
                date_session_id=sess.id,
            )
            db.add(row)
            created.append(row)
    db.commit()
    return created


def score_from_analyses_only(
    db: Session, participant_id: int, candidate_id: int
) -> dict[str, Any]:
    """Fallback scoring without a date — low confidence."""
    a = latest_analysis(db, participant_id)
    b = latest_analysis(db, candidate_id)
    if not a or not b:
        return {
            "compatibility_score": 0.0,
            "confidence": 0.1,
            "score_breakdown": {},
            "positive_evidence": [],
            "potential_mismatches": ["Missing analysis"],
            "unanswered_questions": ["No date session"],
        }
    empty_eval = {
        "compatibility_estimate": 40,
        "confidence": 0.2,
        "potential_friction": [],
        "unanswered_questions": ["No conversation yet"],
    }
    return compute_session_scores(
        analysis_a=public_analysis_view(a),
        analysis_b=public_analysis_view(b),
        eval_a=empty_eval,
        eval_b=empty_eval,
        transcript=[],
    )
