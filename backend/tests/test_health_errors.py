def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["llm_configured"] is False


def test_missing_participant(client):
    assert client.get("/api/participants/99999").status_code == 404


def test_live_run_requires_llm(client):
    # Need two participants first
    for i, name in enumerate(["A One", "B Two"]):
        client.post(
            "/api/participants",
            json={
                "display_name": name,
                "linkedin_url": f"https://www.linkedin.com/in/{name.lower().replace(' ', '-')}",
                "instagram_url": f"https://www.instagram.com/{name.lower().replace(' ', '')}",
                "adult_eligibility_confirmed": True,
                "consent_to_agent_dating": True,
                "linkedin_text": f"{name}. Interested in hiking.",
                "instagram_text": f"{name} loves hiking #hiking",
            },
        )
    created = client.post(
        "/api/runs",
        json={"name": "Live Test", "mode": "live", "max_turns": 4, "session_budget": 1},
    )
    assert created.status_code == 201
    run_id = created.json()["id"]
    started = client.post(f"/api/runs/{run_id}/start")
    assert started.status_code == 400
