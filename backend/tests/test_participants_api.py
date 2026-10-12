def test_create_requires_consent(client):
    res = client.post(
        "/api/participants",
        json={
            "display_name": "Test User",
            "linkedin_url": "https://www.linkedin.com/in/test-user",
            "instagram_url": "https://www.instagram.com/testuser",
            "adult_eligibility_confirmed": False,
            "consent_to_agent_dating": True,
            "linkedin_text": "Interested in hiking.",
            "instagram_text": "Love hiking #outdoors",
        },
    )
    assert res.status_code == 422


def test_create_and_delete_participant(client):
    res = client.post(
        "/api/participants",
        json={
            "display_name": "Test User",
            "linkedin_url": "https://www.linkedin.com/in/test-user",
            "instagram_url": "https://www.instagram.com/testuser",
            "adult_eligibility_confirmed": True,
            "consent_to_agent_dating": True,
            "linkedin_text": "Test User. Interested in hiking and cooking.",
            "instagram_text": "Test User enjoys hiking #outdoors",
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert body["consent_status"] == "granted"
    assert body["is_synthetic"] is False
    assert len(body["sources"]) == 2
    assert body["sources"][0]["acquisition_method"] == "participant_authorized_text"
    pid = body["id"]

    got = client.get(f"/api/participants/{pid}")
    assert got.status_code == 200

    deleted = client.delete(f"/api/participants/{pid}")
    assert deleted.status_code == 204
    assert client.get(f"/api/participants/{pid}").status_code == 404


def test_analyze_with_deterministic_fallback(client):
    res = client.post(
        "/api/participants",
        json={
            "display_name": "Alex Example",
            "linkedin_url": "https://www.linkedin.com/in/alex-example",
            "instagram_url": "https://www.instagram.com/alexexample",
            "adult_eligibility_confirmed": True,
            "consent_to_agent_dating": True,
            "linkedin_text": "Alex Example. Interested in sailing. Looking for curious partners.",
            "instagram_text": "Alex Example. Love sailing #sailing and cooking.",
        },
    )
    pid = res.json()["id"]
    analysis = client.post(f"/api/participants/{pid}/analyze")
    assert analysis.status_code == 200
    data = analysis.json()
    assert data["model_name"].startswith("deterministic")
    assert "summary" in data
    assert isinstance(data["interests"], list)
