from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.schemas.dating import AgentEvaluationSchema, AgentMessageSchema
from app.services.heuristics import related
from app.services.llm import LLMError, LLMProvider

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# profile_view key -> the kind of talking point it yields
_CARD_SOURCES = (
    ("hobby", "hobbies"),
    ("interest", "interests"),
    ("value", "core_values"),
    ("trait", "personality_traits"),
)


def _lower_first(text: str) -> str:
    """Lowercase a label for mid-sentence use, leaving acronyms like "AI" alone."""
    if len(text) > 1 and text[0].isupper() and not text[1].isupper():
        return text[0].lower() + text[1:]
    return text


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(i for i in items if i))


class ParticipantAgent:
    """Independent agent bound to one person's profile analysis.

    It never sees the other person's profile — only what their agent says.
    """

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
        self.first_name = (display_name.split() or ["them"])[0]
        self.profile_view = profile_view
        self.llm = llm or LLMProvider()
        self.conversation: list[dict[str, Any]] = []
        self.questions_to_resolve = list(profile_view.get("missing_information") or [])[:5]
        interests = profile_view.get("interests") or []
        self.dating_objective = (
            f"Represent {display_name} honestly, find out whether the other person meets "
            f"their needs, explore shared ground ({', '.join(self._labels(interests)[:4]) or 'unknown'}), "
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

    @staticmethod
    def _card(kind: str, item: Any) -> dict[str, str]:
        if isinstance(item, dict):
            return {
                "kind": kind,
                "label": str(item.get("value", "")),
                "evidence": str(item.get("evidence", "")),
                "source": str(item.get("source_type", "")),
            }
        return {"kind": kind, "label": str(item), "evidence": "", "source": ""}

    def _cards(self) -> list[dict[str, str]]:
        """Talking points about this person, interleaved by kind for variety."""
        columns = [
            [self._card(kind, item) for item in self.profile_view.get(key) or []]
            for kind, key in _CARD_SOURCES
        ]
        cards: list[dict[str, str]] = []
        for row in range(max((len(c) for c in columns), default=0)):
            cards.extend(c[row] for c in columns if row < len(c) and c[row]["label"])
        return cards

    def _needs(self) -> list[dict[str, str]]:
        items = list(self.profile_view.get("needs") or []) or list(
            self.profile_view.get("explicitly_stated_preferences") or []
        )
        return [c for c in (self._card("need", i) for i in items) if c["label"]]

    def _quote(self, card: dict[str, str]) -> str:
        evidence = card["evidence"].strip()
        if len(evidence) < 12 or evidence.lower() == card["label"].lower():
            return ""
        if len(evidence) > 140:
            evidence = evidence[:140].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"
        source = {"linkedin": "LinkedIn", "instagram": "Instagram"}.get(card["source"], "profile")
        return f" — their {source} says “{evidence}”"

    def _share(self, card: dict[str, str], variant: int = 0) -> str:
        """One sentence presenting a talking point, with its supporting quote."""
        label = _lower_first(card["label"])
        quote = self._quote(card)
        me = self.first_name
        templates = {
            "hobby": (
                f"{label} is a real part of {me}'s life{quote}.",
                f"{me} makes time for {label}{quote}.",
                f"you'll often find {me} doing something around {label}{quote}.",
            ),
            "interest": (
                f"{me} spends a lot of thought on {label}{quote}.",
                f"{me} keeps coming back to {label}{quote}.",
                f"{label} is something {me} clearly cares about{quote}.",
            ),
            "value": (
                f"underneath it all, {me} cares about {label}{quote}.",
                f"what drives {me} is {label}{quote}.",
            ),
            "trait": (
                f"as a person, {me} comes across as {label}{quote}.",
                f"the way {me} shows up is {label}{quote}.",
            ),
            "need": (f"what {me} is looking for is {label}{quote}.",),
        }[card["kind"]]
        return templates[variant % len(templates)]

    def _split(self, transcript: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        mine = [m for m in transcript if m.get("speaker_participant_id") == self.participant_id]
        theirs = [m for m in transcript if m.get("speaker_participant_id") != self.participant_id]
        return mine, theirs

    @staticmethod
    def _raised(entries: list[dict[str, Any]]) -> list[str]:
        return _unique([str(t) for m in entries for t in m.get("referenced_interests") or []])

    def deterministic_turn(
        self,
        *,
        turn_index: int,
        max_turns: int,
        peer_name: str,
        transcript: list[dict[str, Any]],
    ) -> AgentMessageSchema:
        """Rule-based turn: react to the other agent, share something new, probe a need."""
        me = self.first_name
        peer = (peer_name.split() or ["them"])[0]
        cards, needs = self._cards(), self._needs()
        mine, theirs = self._split(transcript)
        already_said = set(self._raised(mine))
        their_topics = self._raised(theirs)
        last_peer = theirs[-1] if theirs else None

        if turn_index == 0:
            lead = cards[0] if cards else None
            headline = str(self.profile_view.get("headline") or "").strip()
            intro = f" In one line: {headline}." if headline else ""
            opener = (
                f" The first thing you should know: {self._share(lead)}"
                if lead
                else " Their public profiles are thin, so I'll be upfront about what I don't know."
            )
            return AgentMessageSchema(
                message=(
                    f"Hi! I'm {me}'s agent — I've read {me}'s LinkedIn and Instagram and "
                    f"I'm here on their behalf.{intro}{opener}"
                ),
                question=f"What does {peer} do when nobody is asking them to work?",
                referenced_interests=[lead["label"]] if lead else [],
                intent="open",
                confidence=0.6 if lead else 0.25,
            )

        if turn_index >= max_turns - 2:
            shared = _unique(
                [c["label"] for c in cards for t in their_topics if related(c["label"], t)]
            )
            met = [n["label"] for n in needs if any(related(n["label"], t) for t in their_topics)]
            open_needs = [n["label"] for n in needs if n["label"] not in met]
            parts = [
                f"Here's my honest read for {me}: real common ground on "
                + ", ".join(_lower_first(s) for s in shared[:3])
                + "."
                if shared
                else f"Here's my honest read: I didn't find much overlap between what {me} and {peer} show publicly."
            ]
            if met:
                parts.append(f"{peer} looks like a fit for {me}'s need for {_lower_first(met[0])}.")
            if open_needs:
                parts.append(f"What I couldn't confirm: {_lower_first(open_needs[0])}.")
            idea = str(self.profile_view.get("ideal_date") or "").strip()
            if shared and idea:
                parts.append(f"If they do meet, my suggestion for {me}: {_lower_first(idea)}")
            return AgentMessageSchema(
                message=" ".join(parts),
                question="",
                referenced_interests=shared[:4],
                intent="close",
                confidence=0.6 if shared else 0.4,
            )

        parts: list[str] = []
        referenced: list[str] = []
        fresh_topics = [str(t) for t in (last_peer or {}).get("referenced_interests") or []]
        their_question = str((last_peer or {}).get("question") or "").lower()

        # 1. Answer the need the other agent just asked about, from evidence only.
        asked = next((t for t in reversed(fresh_topics) if t.lower() in their_question), None)
        if asked:
            proof = next((c for c in cards if related(c["label"], asked)), None)
            if proof:
                parts.append(f"To your question — yes, I think so: {self._share(proof, turn_index)}")
                referenced.append(proof["label"])
                # Repeat their wording so the other agent can tell the need was met.
                referenced.append(asked)
            else:
                parts.append(
                    f"To your question — I can't honestly confirm that. Nothing on {me}'s "
                    f"LinkedIn or Instagram speaks to {_lower_first(asked)}."
                )

        # 2. React to something new they shared about their person.
        news = [t for t in fresh_topics if t != asked and t not in already_said]
        heard = news or ([] if asked else [str((last_peer or {}).get("message") or "")])
        match = next(
            (
                c
                for t in heard
                for c in cards + needs
                if t and c["label"] not in referenced and related(c["label"], t)
            ),
            None,
        )
        if match:
            parts.append(f"And that lands on {me}'s side too: {self._share(match, turn_index + 1)}")
            referenced.append(match["label"])
        elif news and not asked:
            parts.append(
                f"{news[0]} isn't something I can find on {me}'s public profiles, "
                "so I won't pretend it is."
            )
        elif last_peer and not asked and not news:
            parts.append(
                f"On “{str(last_peer.get('message') or '')[:120]}” — I can't see that on "
                f"{me}'s public profiles, so I won't claim it."
            )

        # 3. Offer something new about my person.
        fresh = next(
            (c for c in cards if c["label"] not in already_said and c["label"] not in referenced),
            None,
        )
        if fresh:
            parts.append(f"Something you haven't heard yet: {self._share(fresh, turn_index)}")
            referenced.append(fresh["label"])

        # 4. Probe one of my person's needs.
        need = next((n for n in needs if n["label"] not in already_said), None)
        if need:
            question = f"{me} seems to need {_lower_first(need['label'])}. Is that {peer}?"
            referenced.append(need["label"])
        else:
            question = f"What would {peer} want {me} to know before a first date?"

        return AgentMessageSchema(
            message=" ".join(parts) or f"I'd like to understand {peer} better.",
            question=question,
            referenced_interests=_unique(referenced),
            intent="learn_preferences" if need else "share_interest",
            confidence=0.55 if cards else 0.3,
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
            return msg, False, "rule-based-agent-v2"

        system = (PROMPTS_DIR / "dating_v2.txt").read_text(encoding="utf-8")
        user = json.dumps(
            {
                "your_person": self.display_name,
                "dating_objective": self.dating_objective,
                "profile": self.profile_view,
                "other_person": peer_name,
                "turn_index": turn_index,
                "max_turns": max_turns,
                "is_your_final_turn": turn_index >= max_turns - 2,
                "transcript": self._readable(transcript, peer_name),
                "instruction": "Produce your next turn as JSON.",
            },
            ensure_ascii=False,
        )
        try:
            validated, model = await self.llm.complete_json(
                system_prompt=system,
                user_prompt=user,
                schema_model=AgentMessageSchema,
                temperature=0.7,
            )
            return validated, True, model
        except LLMError:
            # Honest fallback — the message is labeled as rule-based, not live
            msg = self.deterministic_turn(
                turn_index=turn_index,
                max_turns=max_turns,
                peer_name=peer_name,
                transcript=transcript,
            )
            return msg, False, "rule-based-agent-v2-after-llm-failure"

    def _readable(self, transcript: list[dict[str, Any]], peer_name: str) -> list[dict[str, str]]:
        return [
            {
                "speaker": "you"
                if m.get("speaker_participant_id") == self.participant_id
                else f"{peer_name}'s agent",
                "message": str(m.get("message") or ""),
                "question": str(m.get("question") or ""),
            }
            for m in transcript
        ]

    def deterministic_evaluation(
        self, transcript: list[dict[str, Any]], peer_name: str = ""
    ) -> AgentEvaluationSchema:
        """Score the date from this person's side, using only what the other agent disclosed."""
        me = self.first_name
        peer = (peer_name.split() or ["they"])[0]
        cards, needs = self._cards(), self._needs()
        _, theirs = self._split(transcript)
        their_topics = self._raised(theirs)

        def disclosed(label: str) -> bool:
            return any(related(label, topic) for topic in their_topics)

        shared = _unique([c["label"] for c in cards if disclosed(c["label"])])
        met = [n["label"] for n in needs if disclosed(n["label"])]
        unmet = [n["label"] for n in needs if n["label"] not in met]
        need_ratio = len(met) / len(needs) if needs else 0.0

        score = (
            30.0
            + 35.0 * need_ratio
            + min(25.0, 6.0 * len(shared))
            + min(10.0, 1.5 * len(transcript))
        )
        confidence = min(
            0.85,
            0.3 + 0.07 * len(shared) + 0.08 * len(met) + (0.05 if len(transcript) >= 6 else 0.0),
        )
        if score >= 70:
            verdict = f"{peer} looks like a strong fit for {me}."
        elif score >= 55:
            verdict = f"{peer} is a promising match for {me}, with a few open questions."
        elif score >= 42:
            verdict = f"Pleasant, but {me} and {peer} share only a little."
        else:
            verdict = f"Not much evidence that {peer} fits what {me} needs."

        impression = (
            f"From {me}'s side there is common ground on {', '.join(_lower_first(s) for s in shared[:3])}. "
            if shared
            else f"From {me}'s side there is little confirmed common ground. "
        )
        if met:
            impression += f"{peer} appears to meet {me}'s need for {_lower_first(met[0])}."
        elif needs:
            impression += f"None of {me}'s needs were clearly met in what {peer}'s agent shared."

        return AgentEvaluationSchema(
            verdict=verdict,
            overall_impression=impression.strip(),
            shared_interests=shared[:8],
            needs_met=met[:6],
            needs_unmet=unmet[:6],
            potential_friction=[f"No sign yet of: {_lower_first(n)}" for n in unmet[:3]],
            unanswered_questions=self.questions_to_resolve[:3],
            compatibility_estimate=round(min(100.0, score), 1),
            confidence=round(confidence, 2),
            reasoning=(
                f"Rule-based: {len(met)}/{len(needs)} of {me}'s needs matched by what "
                f"{peer}'s agent disclosed, {len(shared)} shared topics, {len(transcript)} turns."
            ),
        )

    async def evaluate(
        self,
        transcript: list[dict[str, Any]],
        peer_name: str = "",
        *,
        force_deterministic: bool = False,
    ) -> tuple[AgentEvaluationSchema, bool, str]:
        if force_deterministic or not self.llm.configured:
            return (
                self.deterministic_evaluation(transcript, peer_name),
                False,
                "rule-based-eval-v2",
            )
        system = (PROMPTS_DIR / "evaluation_v2.txt").read_text(encoding="utf-8")
        user = json.dumps(
            {
                "your_person": self.display_name,
                "profile": self.profile_view,
                "other_person": peer_name,
                "transcript": self._readable(transcript, peer_name),
            },
            ensure_ascii=False,
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
                self.deterministic_evaluation(transcript, peer_name),
                False,
                "rule-based-eval-v2-after-llm-failure",
            )
