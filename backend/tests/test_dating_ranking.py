from app.ranking.engine import compute_session_scores
from app.services.dating import ordered_ids, unique_pairs


def test_unique_pairs_no_self():
    pairs = unique_pairs([1, 2, 3, 4])
    assert len(pairs) == 6
    assert all(a < b for a, b in pairs)
    assert all(a != b for a, b in pairs)


def test_ordered_ids_rejects_self():
    try:
        ordered_ids(5, 5)
        assert False
    except ValueError:
        assert True


def test_ranking_determinism():
    analysis_a = {
        "interests": [{"value": "hiking"}, {"value": "cooking"}],
        "hobbies": [{"value": "yoga"}],
        "explicitly_stated_preferences": [{"value": "kind communication"}],
        "lifestyle_clues": [{"value": "outdoors"}],
        "relationship_preferences": [],
    }
    analysis_b = {
        "interests": [{"value": "hiking"}, {"value": "chess"}],
        "hobbies": [{"value": "yoga"}],
        "explicitly_stated_preferences": [{"value": "kind communication"}],
        "lifestyle_clues": [{"value": "outdoors"}],
        "relationship_preferences": [],
    }
    eval_a = {
        "compatibility_estimate": 70,
        "confidence": 0.6,
        "potential_friction": [],
        "unanswered_questions": ["schedule"],
    }
    eval_b = {
        "compatibility_estimate": 72,
        "confidence": 0.58,
        "potential_friction": ["distance unknown"],
        "unanswered_questions": [],
    }
    transcript = [{"message": "hi"}] * 6
    s1 = compute_session_scores(
        analysis_a=analysis_a,
        analysis_b=analysis_b,
        eval_a=eval_a,
        eval_b=eval_b,
        transcript=transcript,
    )
    s2 = compute_session_scores(
        analysis_a=analysis_a,
        analysis_b=analysis_b,
        eval_a=eval_a,
        eval_b=eval_b,
        transcript=transcript,
    )
    assert s1["compatibility_score"] == s2["compatibility_score"]
    assert s1["confidence"] == s2["confidence"]
    assert "hiking" in s1["shared_interests"]


def test_missing_evidence_low_confidence():
    empty = {
        "interests": [],
        "hobbies": [],
        "explicitly_stated_preferences": [],
        "lifestyle_clues": [],
        "relationship_preferences": [],
    }
    eval_x = {
        "compatibility_estimate": 40,
        "confidence": 0.2,
        "potential_friction": [],
        "unanswered_questions": [],
    }
    scored = compute_session_scores(
        analysis_a=empty,
        analysis_b=empty,
        eval_a=eval_x,
        eval_b=eval_x,
        transcript=[],
    )
    assert scored["confidence"] < 0.5
