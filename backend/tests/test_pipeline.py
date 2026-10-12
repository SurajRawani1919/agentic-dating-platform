"""Links in → profile page → dating → personal rankings → saved example."""

from sqlalchemy.orm import sessionmaker

from app.agents.participant_agent import ParticipantAgent
from app.models import DemoRun, Participant
from app.services.analysis import deterministic_analysis
from app.services.evidence import evidence_supported
from app.services.participants import SourceAcquisitionError
from app.source_providers.base import AcquisitionResult

LINKEDIN_TEXT = """[LinkedIn public profile — https://www.linkedin.com/in/jane-doe]
Name: Jane Doe
Headline: Staff Engineer at Tidewater
Location: Lisbon, Portugal
About: Climate engineer and founder of a tidal energy startup. Voracious reader. I mentor students every week.
Recent LinkedIn posts they wrote or shared:
- "Spent the week mentoring students on renewable energy research."
"""

INSTAGRAM_TEXT = """[Instagram public profile — https://www.instagram.com/jane.doe]
Name: Jane Doe
Username: @jane.doe
Bio: Runs up hills, bakes on Sundays
Recent Instagram posts (newest first):
1. Sunrise trail running on the Sintra ridge with friends #trailrunning
2. Third attempt at baking croissants. Getting closer.
3. Weekend travel: a slow road trip down the coast with a camera.
"""


def _add(client, name: str, linkedin_text: str, instagram_text: str) -> dict:
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
    return res.json()


# ---- analysis ---------------------------------------------------------------


def test_rule_based_analysis_covers_needs_hobbies_interests_and_qualities():
    result = deterministic_analysis(LINKEDIN_TEXT, INSTAGRAM_TEXT)
    hobbies = {h["value"] for h in result["hobbies"]}
    interests = {i["value"] for i in result["interests"]}
    assert {"Running", "Cooking and food", "Travel"} <= hobbies
    assert "Climate and sustainability" in interests
    assert result["needs"], "needs must be inferred"
    assert result["values"] and result["personality_traits"]
    assert result["headline"] == "Staff Engineer at Tidewater"
    assert "Jane Doe" in result["summary"]
    assert result["ideal_date"]
    assert any(c["value"].startswith("Based in Lisbon") for c in result["lifestyle_clues"])


def test_every_rule_based_claim_quotes_its_source():
    result = deterministic_analysis(LINKEDIN_TEXT, INSTAGRAM_TEXT)
    sources = {"linkedin": LINKEDIN_TEXT, "instagram": INSTAGRAM_TEXT}
    for key in ("needs", "hobbies", "interests", "values", "personality_traits"):
        for item in result[key]:
            assert evidence_supported(item["evidence"], sources[item["source_type"]]), (key, item)
    assert all(need["why"] for need in result["needs"])


def test_analysis_never_reads_the_source_header_line():
    # "linkedin"/"instagram"/"profile" in the bracketed header must not become evidence
    result = deterministic_analysis(LINKEDIN_TEXT, INSTAGRAM_TEXT)
    for key in ("hobbies", "interests", "needs"):
        assert all("public profile —" not in item["evidence"] for item in result[key])


# ---- links in → profile page ------------------------------------------------


def test_pasting_links_yields_an_analyzed_profile_in_one_call(client):
    person = _add(client, "Jane Doe", LINKEDIN_TEXT, INSTAGRAM_TEXT)
    assert person["has_analysis"] is True
    assert person["headline"] == "Staff Engineer at Tidewater"
    # the profile page can show exactly what the agent read
    assert any("Runs up hills" in s["content"] for s in person["sources"])

    analysis = client.get(f"/api/participants/{person['id']}/analysis").json()
    for field in ("needs", "hobbies", "interests", "core_values", "personality_traits"):
        assert analysis[field], field
    # list view stays light: no full source text
    listed = client.get("/api/participants").json()["items"][0]
    assert all(s["content"] == "" for s in listed["sources"])


def test_name_is_taken_from_the_profiles_when_left_blank(client, monkeypatch):
    def fake_read(payload):
        return (
            AcquisitionResult("linkedin", payload.linkedin_url, "linkedin_public_page", "acquired", LINKEDIN_TEXT, display_name="Jane Doe"),
            AcquisitionResult("instagram", payload.instagram_url, "instagram_crawler_rendered_page", "acquired", INSTAGRAM_TEXT, display_name="Jane Doe"),
        )

    monkeypatch.setattr("app.services.participants._read_sources", fake_read)
    res = client.post(
        "/api/participants",
        json={
            "linkedin_url": "linkedin.com/in/jane-doe",
            "instagram_url": "instagram.com/jane.doe",
            "adult_eligibility_confirmed": True,
            "consent_to_agent_dating": True,
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["display_name"] == "Jane Doe"
    assert body["source_verification_status"] == "plausibly_matched"
    assert {s["acquisition_status"] for s in body["sources"]} == {"acquired"}


def test_same_links_twice_do_not_duplicate_the_person(client):
    first = _add(client, "Jane Doe", LINKEDIN_TEXT, INSTAGRAM_TEXT)
    second = _add(client, "Jane Doe", LINKEDIN_TEXT, INSTAGRAM_TEXT)
    assert first["id"] == second["id"]
    assert client.get("/api/participants").json()["total"] == 1


def test_unreadable_or_private_profiles_are_refused_with_a_reason(client, monkeypatch):
    def private(payload):
        raise SourceAcquisitionError("That Instagram profile is private.")

    monkeypatch.setattr("app.services.participants._read_sources", private)
    res = client.post(
        "/api/participants",
        json={
            "linkedin_url": "https://www.linkedin.com/in/jane-doe",
            "instagram_url": "https://www.instagram.com/jane.doe",
            "adult_eligibility_confirmed": True,
            "consent_to_agent_dating": True,
        },
    )
    assert res.status_code == 422
    assert "private" in res.json()["detail"]
    assert client.get("/api/participants").json()["total"] == 0


def test_no_content_at_all_is_refused(client):
    # scraping is off in tests and no profile text was pasted
    res = client.post(
        "/api/participants",
        json={
            "linkedin_url": "https://www.linkedin.com/in/jane-doe",
            "instagram_url": "https://www.instagram.com/jane.doe",
            "adult_eligibility_confirmed": True,
            "consent_to_agent_dating": True,
        },
    )
    assert res.status_code == 422
    assert "Neither profile could be read" in res.json()["detail"]


# ---- the agents date --------------------------------------------------------


def _agent(pid: int, name: str, linkedin_text: str, instagram_text: str) -> ParticipantAgent:
    result = deterministic_analysis(linkedin_text, instagram_text, name)
    view = {
        "headline": result["headline"],
        "needs": result["needs"],
        "hobbies": result["hobbies"],
        "interests": result["interests"],
        "core_values": result["values"],
        "personality_traits": result["personality_traits"],
        "ideal_date": result["ideal_date"],
        "missing_information": result["missing_information"],
    }
    return ParticipantAgent(pid, name, view)


def _date(a: ParticipantAgent, b: ParticipantAgent, turns: int = 6) -> list[dict]:
    transcript: list[dict] = []
    speakers = [a, b]
    for turn in range(turns):
        speaker, peer = speakers[turn % 2], speakers[(turn + 1) % 2]
        msg = speaker.deterministic_turn(
            turn_index=turn, max_turns=turns, peer_name=peer.display_name, transcript=transcript
        )
        transcript.append(
            {
                "speaker_participant_id": speaker.participant_id,
                "message": msg.message,
                "question": msg.question,
                "intent": msg.intent,
                "referenced_interests": msg.referenced_interests,
            }
        )
    return transcript


OTHER_LINKEDIN = LINKEDIN_TEXT.replace("Jane Doe", "Sam Roe")
OTHER_INSTAGRAM = INSTAGRAM_TEXT.replace("Jane Doe", "Sam Roe").replace("jane.doe", "sam.roe")
STRANGER_LINKEDIN = "Name: Kit Lane\nHeadline: Tax accountant\nAbout: Enjoys chess and golf."
STRANGER_INSTAGRAM = "Name: Kit Lane\nBio: Golf every weekend\n1. Chess club night"


def test_agents_hold_a_real_exchange_and_close_with_a_verdict():
    jane = _agent(1, "Jane Doe", LINKEDIN_TEXT, INSTAGRAM_TEXT)
    sam = _agent(2, "Sam Roe", OTHER_LINKEDIN, OTHER_INSTAGRAM)
    transcript = _date(jane, sam)

    assert transcript[0]["intent"] == "open"
    assert "Jane's agent" in transcript[0]["message"]
    assert transcript[-1]["intent"] == "close" and transcript[-2]["intent"] == "close"
    # the middle turns react to the other side, probe a need, and answer the one asked
    middle = transcript[1:-2]
    assert any("that lands on" in m["message"] for m in middle)
    assert all(m["question"] for m in middle)
    assert any("seems to need" in m["question"] for m in middle)
    assert any(m["message"].startswith("To your question") for m in middle[1:])
    # agents do not repeat the same talking point
    raised = [t for m in transcript if m["speaker_participant_id"] == 1 for t in m["referenced_interests"]]
    assert len(set(raised)) >= 3


def test_agent_verdict_is_higher_for_a_better_fit():
    jane = _agent(1, "Jane Doe", LINKEDIN_TEXT, INSTAGRAM_TEXT)
    sam = _agent(2, "Sam Roe", OTHER_LINKEDIN, OTHER_INSTAGRAM)
    kit = _agent(3, "Kit Lane", STRANGER_LINKEDIN, STRANGER_INSTAGRAM)

    with_sam = jane.deterministic_evaluation(_date(jane, sam), "Sam Roe")
    with_kit = jane.deterministic_evaluation(_date(jane, kit), "Kit Lane")
    assert with_sam.compatibility_estimate > with_kit.compatibility_estimate
    assert with_sam.shared_interests and with_sam.needs_met
    assert with_sam.verdict and with_kit.verdict


def test_agent_admits_what_is_not_on_the_profiles():
    kit = _agent(3, "Kit Lane", STRANGER_LINKEDIN, STRANGER_INSTAGRAM)
    reply = kit.deterministic_turn(
        turn_index=1,
        max_turns=6,
        peer_name="Jane Doe",
        transcript=[
            {
                "speaker_participant_id": 1,
                "message": "Jane lives for scuba diving.",
                "question": "Does Kit dive?",
                "intent": "open",
                "referenced_interests": ["Scuba diving"],
            }
        ],
    )
    assert "isn't something I can find on Kit's public profiles" in reply.message


# ---- rankings + saved example -----------------------------------------------


def _run_all(client) -> int:
    from app.workers.run_manager import wait_for_run

    run_id = client.post("/api/runs", json={"name": "Cohort", "mode": "live"}).json()["id"]
    assert client.post(f"/api/runs/{run_id}/start").status_code == 200
    assert wait_for_run(run_id, timeout=60)
    assert client.get(f"/api/runs/{run_id}").json()["status"] == "completed"
    return run_id


def test_everyone_dates_everyone_and_gets_a_personal_ranking(client):
    jane = _add(client, "Jane Doe", LINKEDIN_TEXT, INSTAGRAM_TEXT)["id"]
    sam = _add(client, "Sam Roe", OTHER_LINKEDIN, OTHER_INSTAGRAM)["id"]
    kit = _add(client, "Kit Lane", STRANGER_LINKEDIN, STRANGER_INSTAGRAM)["id"]
    run_id = _run_all(client)

    assert len(client.get(f"/api/runs/{run_id}/sessions").json()) == 3
    for person in (jane, sam, kit):
        rows = client.get(f"/api/rankings/{person}").json()["rankings"]
        assert [r["rank"] for r in rows] == [1, 2]
        assert rows[0]["compatibility_score"] >= rows[1]["compatibility_score"]
        assert person not in {r["candidate_id"] for r in rows}

    # Jane's best fit is the person who shares her life, not the stranger
    top = client.get(f"/api/rankings/{jane}").json()["rankings"][0]
    assert top["candidate_id"] == sam
    assert top["score_breakdown"]["personal_fit"]["verdict"]
    assert top["date_session_id"]


def test_demo_prefers_a_finished_real_run_over_the_synthetic_sample(client):
    for name, li, ig in (
        ("Jane Doe", LINKEDIN_TEXT, INSTAGRAM_TEXT),
        ("Sam Roe", OTHER_LINKEDIN, OTHER_INSTAGRAM),
    ):
        _add(client, name, li, ig)
    run_id = _run_all(client)

    demo = client.get("/api/demo").json()
    assert demo["is_real"] is True
    assert demo["run"]["id"] == run_id
    assert demo["participant_count"] == 2
    assert demo["showcase_date_ids"]
    assert len(demo["top_matches"]) == 2


def test_snapshot_round_trip_restores_the_finished_example(client, db, tmp_path):
    from app import cohort

    for name, li, ig in (
        ("Jane Doe", LINKEDIN_TEXT, INSTAGRAM_TEXT),
        ("Sam Roe", OTHER_LINKEDIN, OTHER_INSTAGRAM),
        ("Kit Lane", STRANGER_LINKEDIN, STRANGER_INSTAGRAM),
    ):
        _add(client, name, li, ig)
    _run_all(client)

    path = cohort.export_snapshot(tmp_path / "snapshot.json")

    # wipe everything, as on a fresh deployment
    for model in (DemoRun, Participant):
        for row in db.query(model).all():
            db.delete(row)
    db.commit()
    assert client.get("/api/participants").json()["total"] == 0

    new_run = cohort.import_snapshot(path, sessionmaker(bind=db.get_bind())())
    db.expire_all()

    people = client.get("/api/participants").json()["items"]
    assert [p["display_name"] for p in people] == ["Jane Doe", "Sam Roe", "Kit Lane"]
    assert all(p["has_analysis"] for p in people)
    demo = client.get("/api/demo").json()
    assert demo["is_real"] and demo["run"]["id"] == new_run and demo["ranking_count"] == 6
    transcript = client.get(f"/api/dates/{demo['showcase_date_ids'][0]}/transcript").json()
    assert len(transcript["messages"]) == 6
    ranking = client.get(f"/api/rankings/{people[0]['id']}").json()["rankings"]
    assert ranking[0]["candidate_name"] == "Sam Roe"
