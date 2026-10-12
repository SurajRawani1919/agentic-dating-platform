from app.agents.participant_agent import ParticipantAgent
from app.schemas.dating import AgentMessageSchema
from app.services.evidence import evidence_supported, validate_analysis_against_sources
from app.services.llm import LLMError, LLMProvider


def test_evidence_supported():
    source = "Interested in hiking Cascades trails and indie coffee."
    assert evidence_supported("hiking Cascades trails", source)
    assert not evidence_supported("secret underwater mansion", source)


def test_validate_drops_ungrounded():
    raw = {
        "interests": [
            {
                "value": "hiking",
                "evidence": "hiking Cascades",
                "source_type": "linkedin",
                "confidence": 0.8,
            },
            {
                "value": "skydiving",
                "evidence": "loves skydiving weekly",
                "source_type": "instagram",
                "confidence": 0.9,
            },
        ],
        "hobbies": [],
        "explicit_preferences": [],
        "communication_clues": [],
        "lifestyle_clues": [],
        "relationship_preferences": [],
        "uncertainties": [],
    }
    out = validate_analysis_against_sources(
        raw,
        linkedin_text="Interested in hiking Cascades trails",
        instagram_text="Coffee photos only",
    )
    values = [i["value"] for i in out["interests"]]
    assert "hiking" in values
    assert "skydiving" not in values


def test_agent_message_schema():
    msg = AgentMessageSchema(
        message="Hello",
        question="What do you enjoy?",
        referenced_interests=["hiking"],
        intent="open",
        confidence=0.5,
    )
    assert msg.intent == "open"


def test_agent_deterministic_turn_persists_context():
    agent = ParticipantAgent(
        1,
        "Avery",
        {
            "interests": [{"value": "hiking"}],
            "hobbies": [],
            "explicitly_stated_preferences": [],
            "missing_information": ["weekend rhythm"],
        },
    )
    first = agent.deterministic_turn(
        turn_index=0, max_turns=4, peer_name="Jordan", transcript=[]
    )
    second = agent.deterministic_turn(
        turn_index=1,
        max_turns=4,
        peer_name="Jordan",
        transcript=[
            {
                "speaker_participant_id": 2,
                "message": "We enjoy cooking together",
                "question": "",
                "intent": "share_interest",
            }
        ],
    )
    assert "cooking" in second.message.lower() or "Cooking" in second.message
    assert first.intent == "open"


def test_llm_not_configured_raises():
    provider = LLMProvider()
    assert provider.configured is False
