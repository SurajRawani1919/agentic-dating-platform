def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["llm_configured"] is False


def test_missing_participant(client):
    assert client.get("/api/participants/99999").status_code == 404


def _add_person(client, name: str, linkedin_text: str, instagram_text: str) -> int:
    slug = name.lower().replace(" ", "-")
    res = client.post(
        "/api/participants",
        json={
            "display_name": name,
            "linkedin_url": f"https://www.linkedin.com/in/{slug}",
            "instagram_url": f"https://www.instagram.com/{slug.replace('-', '')}",
            "adult_eligibility_confirmed": True,
            "consent_to_agent_dating": True,
            "linkedin_text": linkedin_text,
            "instagram_text": instagram_text,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_run_without_llm_dates_with_rule_based_agents(client):
    """No LLM key must not block dating: rule-based agents date and rankings appear."""
    from app.workers.run_manager import wait_for_run

    a = _add_person(client, "A One", "A One. Interested in hiking.", "A One loves hiking #hiking")
    b = _add_person(client, "B Two", "B Two. Interested in hiking.", "B Two loves hiking #hiking")

    created = client.post("/api/runs", json={"name": "Live Test", "mode": "live", "max_turns": 4})
    assert created.status_code == 201
    run_id = created.json()["id"]
    assert created.json()["config"]["engine"] == "rule-based"

    started = client.post(f"/api/runs/{run_id}/start")
    assert started.status_code == 200
    assert wait_for_run(run_id, timeout=30)

    run = client.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "completed"
    assert run["completed_sessions"] == 1

    session = client.get(f"/api/runs/{run_id}/sessions").json()[0]
    transcript = client.get(f"/api/dates/{session['id']}/transcript").json()
    assert len(transcript["messages"]) == 4
    assert all(m["is_live_llm"] is False for m in transcript["messages"])
    # Both agents filed their own verdict
    assert session["agent_a_feedback"]["verdict"]
    assert session["agent_b_feedback"]["verdict"]

    for person, other in ((a, b), (b, a)):
        ranking = client.get(f"/api/rankings/{person}").json()
        assert [r["candidate_id"] for r in ranking["rankings"]] == [other]
        assert "personal_fit" in ranking["rankings"][0]["score_breakdown"]


def test_run_needs_two_analyzed_people(client):
    _add_person(client, "Solo Person", "Solo Person. Interested in chess.", "Solo #chess")
    res = client.post("/api/runs", json={"name": "Too small", "mode": "live"})
    assert res.status_code == 400
