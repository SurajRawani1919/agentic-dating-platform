from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.schemas.dating import AgentEvaluationSchema, AgentMessageSchema
from app.services.llm import LLMError, LLMProvider

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class ParticipantAgent:
    """Independent agent bound to a single participant's public analysis."""

    def __init__(
        self,
        participant_id: int,
        display_name: str,
        profile_view: dict[str, Any],
        *,
        llm: LLMProvider | None = None,
    ) -> None:
        self.participant_id = participant_id
        self.display_name = display_name
        self.profile_view = profile_view
        self.llm = llm or LLMProvider()
        self.conversation: list[dict[str, Any]] = []
        self.questions_to_resolve = list(profile_view.get("missing_information") or [])[:5]
        interests = profile_view.get("interests") or []
        self.dating_objective = (
            f"Represent {display_name} honestly, learn about compatibility on "
            f"supported interests ({', '.join(self._labels(interests)[:4]) or 'unknown'}), "
            "and never invent personal facts."
        )

    @staticmethod
    def _labels(items: list[Any]) -> list[str]:
        labels: list[str] = []
        for item in items:
            if isinstance(item, dict):
                labels.append(str(item.get("value", "")))
            else:
                labels.append(str(item))
        return [x for x in labels if x]

    def _interest_labels(self) -> list[str]:
        return self._labels(self.profile_view.get("interests") or []) + self._labels(
            self.profile_view.get("hobbies") or []
        )

    def deterministic_turn(
        self,
        *,
        turn_index: int,
        max_turns: int,
        peer_name: str,
        transcript: list[dict[str, Any]],
    ) -> AgentMessageSchema:
        interests = self._interest_labels()
        own = interests[turn_index % len(interests)] if interests else "getting to know people"
        prefs = self._labels(self.profile_view.get("explicitly_stated_preferences") or [])
        missing = self.questions_to_resolve[turn_index % len(self.questions_to_resolve)] if self.questions_to_resolve else "what a good weeknight looks like for you"

        last_peer = next(
            (
                m
                for m in reversed(transcript)
                if m.get("speaker_participant_id") != self.participant_id
            ),
            None,
        )

        if turn_index == 0:
            return AgentMessageSchema(
                message=(
                    f"Hi {peer_name} — I'm representing {self.display_name}. "
                    f"From their profile, {own} comes up with supporting evidence. "
                    f"I'd love to understand what matters to your person."
                ),
                question=f"What role does {own} play in their life, if any?",
                referenced_interests=[own] if interests else [],
                intent="open",
                confidence=0.55 if interests else 0.25,
            )

        if turn_index >= max_turns - 1:
            return AgentMessageSchema(
                message=(
                    f"Thanks for the conversation. For {self.display_name}, the exchange "
                    f"highlighted possible overlap around {own}"
                    + (f" and preferences like {prefs[0]}" if prefs else "")
                    + ". Some questions remain unanswered, which lowers confidence."
                ),
                question="",
                referenced_interests=[own] if interests else [],
                intent="close",
                confidence=0.5,
            )

        reaction = ""
        if last_peer:
            reaction = f"You mentioned: “{(last_peer.get('message') or '')[:120]}”. "

        intent = "learn_preferences" if turn_index % 2 == 1 else "share_interest"
        return AgentMessageSchema(
            message=(
                f"{reaction}For {self.display_name}, I can speak to {own} from their "
                f"permitted profile. I do not know facts that aren't in that evidence. "
                f"One open question on our side: {missing}."
            ),
            question=f"Could you share how your person approaches: {missing}?",
            referenced_interests=[own] if interests else [],
            intent=intent,  # type: ignore[arg-type]
            confidence=0.5 if interests else 0.3,
        )

    async def generate_turn(
        self,
        *,
        turn_index: int,
        max_turns: int,
        peer_name: str,
        transcript: list[dict[str, Any]],
        force_deterministic: bool = False,
    ) -> tuple[AgentMessageSchema, bool, str]:
        """Returns message, is_live_llm, model_name."""
        if force_deterministic or not self.llm.configured:
            msg = self.deterministic_turn(
                turn_index=turn_index,
                max_turns=max_turns,
                peer_name=peer_name,
                transcript=transcript,
            )
            return msg, False, "deterministic-agent-v1"

        system = (PROMPTS_DIR / "dating_v1.txt").read_text(encoding="utf-8")
        user = json.dumps(
            {
                "your_identity": {
                    "participant_id": self.participant_id,
                    "display_name": self.display_name,
                    "dating_objective": self.dating_objective,
                    "profile": self.profile_view,
                    "questions_to_resolve": self.questions_to_resolve,
                },
                "peer_name": peer_name,
                "turn_index": turn_index,
                "max_turns": max_turns,
                "transcript": transcript,
                "instruction": "Produce the next structured agent message.",
            },
            ensure_ascii=True,
        )
        try:
            validated, model = await self.llm.complete_json(
                system_prompt=system,
                user_prompt=user,
                schema_model=AgentMessageSchema,
                temperature=0.5,
            )
            return validated, True, model
        except LLMError:
            # Honest fallback — caller should surface that live LLM failed
            msg = self.deterministic_turn(
                turn_index=turn_index,
                max_turns=max_turns,
                peer_name=peer_name,
                transcript=transcript,
            )
            return msg, False, "deterministic-agent-v1-after-llm-failure"

    def deterministic_evaluation(
        self, transcript: list[dict[str, Any]], peer_interests: list[str]
    ) -> AgentEvaluationSchema:
        own = set(x.lower() for x in self._interest_labels())
        peer = set(x.lower() for x in peer_interests)
        shared = sorted(own & peer)
        score = 40.0 + min(40.0, len(shared) * 8.0) + min(15.0, len(transcript) * 1.5)
        conf = 0.35 + min(0.4, len(shared) * 0.08)
        return AgentEvaluationSchema(
            overall_impression=(
                f"Conversation for {self.display_name} suggests "
                + (f"shared ground on {', '.join(shared[:3])}." if shared else "limited confirmed overlap.")
            ),
            shared_interests=shared[:8],
            potential_friction=(
                ["Insufficient preference alignment data"]
                if not self._labels(self.profile_view.get("explicitly_stated_preferences") or [])
                else []
            ),
            unanswered_questions=self.questions_to_resolve[:4],
            compatibility_estimate=min(100.0, score),
            confidence=min(1.0, conf),
            reasoning="Deterministic evaluation from interest overlap and transcript length.",
        )

    async def evaluate(
        self,
        transcript: list[dict[str, Any]],
        peer_interests: list[str],
        *,
        force_deterministic: bool = False,
    ) -> tuple[AgentEvaluationSchema, bool, str]:
        if force_deterministic or not self.llm.configured:
            return (
                self.deterministic_evaluation(transcript, peer_interests),
                False,
                "deterministic-eval-v1",
            )
        system = (PROMPTS_DIR / "evaluation_v1.txt").read_text(encoding="utf-8")
        user = json.dumps(
            {
                "agent_name": self.display_name,
                "profile": self.profile_view,
                "peer_interests": peer_interests,
                "transcript": transcript,
            }
        )
        try:
            validated, model = await self.llm.complete_json(
                system_prompt=system,
                user_prompt=user,
                schema_model=AgentEvaluationSchema,
            )
            return validated, True, model
        except LLMError:
            return (
                self.deterministic_evaluation(transcript, peer_interests),
                False,
                "deterministic-eval-v1-after-llm-failure",
            )
