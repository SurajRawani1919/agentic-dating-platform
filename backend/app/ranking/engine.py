from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import DateSession, Ranking
from app.services.analysis import latest_analysis, public_analysis_view
from app.services.heuristics import related

# Session score: how well two people fit each other overall.
# Initial engineering weights — not scientifically validated.
WEIGHTS = {
    "conversation_quality": 0.35,
    "shared_interests": 0.30,
    "needs_and_values": 0.25,
    "lifestyle_compatibility": 0.10,
}

# Personal ranking score: how well a candidate fits one specific person.
# Their own agent's verdict counts most, then the mutual session score,
# then whether the feeling was returned by the other agent.
PERSONAL_WEIGHTS = {"own_agent": 0.5, "mutual_session": 0.3, "their_agent": 0.2}

# Label overlap is a keyword-level signal; it never justifies near-certainty.
_MAX_OVERLAP_CONFIDENCE = 0.8


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


def _counterparts(a: set[str], b: set[str]) -> list[str]:
    """Labels in ``a`` that are about the same thing as some label in ``b``."""
    return sorted(x for x in a if any(related(x, y) for y in b))


def _overlap_score(a: set[str], b: set[str]) -> tuple[float, list[str], float]:
    if not a and not b:
        return 0.0, [], 0.15
    if not a or not b:
        return 10.0, [], 0.25
    shared_a, shared_b = _counterparts(a, b), _counterparts(b, a)
    ratio = (len(shared_a) + len(shared_b)) / (len(a) + len(b))
    score = min(100.0, 20.0 + ratio * 80.0)
    confidence = min(_MAX_OVERLAP_CONFIDENCE, 0.3 + 0.1 * len(shared_a) + 0.05 * min(len(a), len(b)))
    return score, shared_a, confidence


def _needs_fit(
    needs_a: set[str], offer_a: set[str], needs_b: set[str], offer_b: set[str]
) -> tuple[float, list[str], float]:
    """How far each person's needs are answered by what the other brings."""
    if not needs_a and not needs_b:
        return 0.0, [], 0.15
    met_a, met_b = _counterparts(needs_a, offer_b), _counterparts(needs_b, offer_a)
    ratio = (len(met_a) + len(met_b)) / (len(needs_a) + len(needs_b))
    score = min(100.0, 20.0 + ratio * 80.0)
    confidence = min(_MAX_OVERLAP_CONFIDENCE, 0.3 + 0.08 * (len(met_a) + len(met_b)))
    return score, sorted(set(met_a) | set(met_b)), confidence


def compute_session_scores(
    *,
    analysis_a: dict[str, Any],
    analysis_b: dict[str, Any],
    eval_a: dict[str, Any],
    eval_b: dict[str, Any],
    transcript: list[dict[str, Any]],
) -> dict[str, Any]:
    def view(analysis: dict[str, Any]) -> tuple[set[str], set[str], set[str], set[str]]:
        interests = _labels(analysis.get("interests")) | _labels(analysis.get("hobbies"))
        needs = (
            _labels(analysis.get("needs"))
            | _labels(analysis.get("explicitly_stated_preferences"))
            | _labels(analysis.get("relationship_preferences"))
        )
        # What a person brings to a relationship, as far as their profiles show.
        offer = (
            interests
            | _labels(analysis.get("core_values"))
            | _labels(analysis.get("personality_traits"))
        )
        return interests, needs, offer, _labels(analysis.get("lifestyle_clues"))

    interests_a, needs_a, offer_a, life_a = view(analysis_a)
    interests_b, needs_b, offer_b, life_b = view(analysis_b)

    shared_score, shared, shared_conf = _overlap_score(interests_a, interests_b)
    need_score, needs_met, need_conf = _needs_fit(needs_a, offer_a, needs_b, offer_b)
    life_score, life_shared, life_conf = _overlap_score(life_a, life_b)

    # Reciprocal conversation quality from both agents' verdicts + turn depth
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
    if not needs_a or not needs_b:
        insufficient.append("Needs largely unknown on one or both sides")
        need_score = min(need_score, 35.0)
        need_conf = min(need_conf, 0.3)
    if not life_a or not life_b:
        insufficient.append("Lifestyle compatibility insufficiently evidenced")
        life_conf = min(life_conf, 0.3)

    breakdown = {
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
        "shared_interests": {
            "score": round(shared_score, 2),
            "weight": WEIGHTS["shared_interests"],
            "evidence": shared[:8],
            "uncertainty": round(1 - shared_conf, 2),
            "insufficient_reason": insufficient[0] if (not interests_a or not interests_b) else None,
        },
        "needs_and_values": {
            "score": round(need_score, 2),
            "weight": WEIGHTS["needs_and_values"],
            "evidence": needs_met[:8],
            "uncertainty": round(1 - need_conf, 2),
            "insufficient_reason": "Needs unknown" if not needs_a or not needs_b else None,
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
        convo_conf * WEIGHTS["conversation_quality"]
        + shared_conf * WEIGHTS["shared_interests"]
        + need_conf * WEIGHTS["needs_and_values"]
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
        "positive_evidence": shared[:8] + needs_met[:4],
    }


def personal_fit(sess: DateSession, participant_id: int) -> dict[str, Any]:
    """How well the other person in ``sess`` fits ``participant_id`` specifically.

    Rankings are personal, so A's ranking of B can differ from B's ranking of A:
    each side leans on the verdict of its own agent.
    """
    is_a = participant_id == sess.participant_a_id
    own = (sess.agent_a_feedback if is_a else sess.agent_b_feedback) or {}
    theirs = (sess.agent_b_feedback if is_a else sess.agent_a_feedback) or {}
    mutual = float(sess.compatibility_score or 0)
    own_estimate = float(own.get("compatibility_estimate") or mutual)
    their_estimate = float(theirs.get("compatibility_estimate") or mutual)

    score = (
        PERSONAL_WEIGHTS["own_agent"] * own_estimate
        + PERSONAL_WEIGHTS["mutual_session"] * mutual
        + PERSONAL_WEIGHTS["their_agent"] * their_estimate
    )
    confidence = (float(own.get("confidence") or 0) + float(sess.confidence or 0)) / 2.0

    positives = list(
        dict.fromkeys(
            list(own.get("shared_interests") or [])
            + [f"Meets need: {n}" for n in own.get("needs_met") or []]
        )
    ) or list(sess.shared_interests or [])
    return {
        "score": round(max(0.0, min(100.0, score)), 2),
        "confidence": round(max(0.0, min(1.0, confidence)), 3),
        "positive_evidence": positives[:10],
        "potential_mismatches": list(own.get("potential_friction") or sess.potential_friction or [])[:10],
        "unanswered_questions": list(own.get("unanswered_questions") or sess.unanswered_questions or [])[:10],
        "detail": {
            "score": round(score, 2),
            "own_agent_estimate": round(own_estimate, 1),
            "their_agent_estimate": round(their_estimate, 1),
            "mutual_session_score": round(mutual, 2),
            "weights": PERSONAL_WEIGHTS,
            "verdict": own.get("verdict") or own.get("overall_impression") or "",
            "reasoning": own.get("reasoning") or "",
        },
    }


def aggregate_rankings(db: Session, run_id: int) -> list[Ranking]:
    """Build each person's ranking of everyone they dated in a run."""
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
        candidates: list[tuple[dict[str, Any], int, DateSession]] = []
        for other in sorted(participant_ids):
            if other == pid:
                continue
            key = (pid, other) if pid < other else (other, pid)
            sess = pair_map.get(key)
            if not sess or sess.compatibility_score is None:
                continue
            candidates.append((personal_fit(sess, pid), other, sess))
        # Deterministic sort: score desc, confidence desc, candidate id asc
        candidates.sort(key=lambda x: (-x[0]["score"], -x[0]["confidence"], x[1]))
        for rank_i, (fit, cand_id, sess) in enumerate(candidates, start=1):
            row = Ranking(
                run_id=run_id,
                participant_id=pid,
                candidate_id=cand_id,
                rank=rank_i,
                compatibility_score=fit["score"],
                confidence=fit["confidence"],
                score_breakdown={**(sess.score_breakdown or {}), "personal_fit": fit["detail"]},
                positive_evidence=fit["positive_evidence"],
                potential_mismatches=fit["potential_mismatches"],
                unanswered_questions=fit["unanswered_questions"],
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
