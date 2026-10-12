"""Seed a deterministic 25-participant SYNTHETIC sample.

A stand-in so the UI is explorable before any real people are added. It is
labeled synthetic everywhere and is superseded on /demo by the first finished
run over real people (see app.cohort).

Usage:
  python -m app.seed_demo
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app.db.migrate import ensure_schema
from app.db.session import SessionLocal, engine
from app.models import (
    DateMessage,
    DateSession,
    DemoRun,
    Participant,
    ProfileAnalysis,
    Ranking,
    SourceRecord,
)
from app.ranking.engine import aggregate_rankings, compute_session_scores
from app.services.analysis import deterministic_analysis, public_analysis_view
from app.services.dating import unique_pairs

DEMO_RUN_NAME = "PAIRWISE Demo Run — Synthetic Cohort"


PERSONAS: list[dict] = [
    {
        "name": "Avery Chen",
        "slug": "avery-chen-demo",
        "li": "Product designer based in Seattle. Interested in human-centered design, hiking Cascades trails, and indie coffee. Passionate about accessibility. Looking for thoughtful conversation and weekend outdoor plans.",
        "ig": "Weekend backpacking #hiking. Latte art experiments. Sketchbook pages from ferries. Love climbing gyms and farmers markets.",
    },
    {
        "name": "Jordan Blake",
        "slug": "jordan-blake-demo",
        "li": "Software engineer focused on distributed systems. Enjoys board game nights, cooking seasonal menus, and volunteering at coding workshops. Prefer partners who value curiosity and downtime.",
        "ig": "Sourdough loaves #baking. Catan tournament nights. City bike rides. Looking for someone who enjoys slow dinners.",
    },
    {
        "name": "Sam Rivera",
        "slug": "sam-rivera-demo",
        "li": "Public health analyst. Interested in community gardens, documentary film, and long walks. Passionate about nutrition education. Looking for kind communication.",
        "ig": "Community garden tomatoes #gardening. Film festival snaps. Morning trail runs. Cookbooks stacked on weekends.",
    },
    {
        "name": "Riley Okonkwo",
        "slug": "riley-okonkwo-demo",
        "li": "Jazz pianist and music teacher. Enjoys live shows, vinyl collecting, and teaching improvisation. Prefer evenings with music and quiet mornings.",
        "ig": "Club sets #jazz. Vinyl shelves. Piano practice notes. Coffee before rehearsals.",
    },
    {
        "name": "Casey Nguyen",
        "slug": "casey-nguyen-demo",
        "li": "Climate research associate. Interested in sailing, open-source mapping, and coastal cleanup. Looking for partners who enjoy outdoors and learning.",
        "ig": "Sailboat weekends #sailing. Tide charts. Beach cleanups. Maps and thermos coffee.",
    },
    {
        "name": "Morgan Ellis",
        "slug": "morgan-ellis-demo",
        "li": "Cookbook editor. Passionate about regional cuisines, farmers markets, and reading fiction. Prefer low-key date ideas and good conversation.",
        "ig": "Market hauls #farmersmarket. Annotated cookbooks. Neighborhood bakery reviews. Rainy reading nooks.",
    },
    {
        "name": "Taylor Brooks",
        "slug": "taylor-brooks-demo",
        "li": "UX researcher. Enjoys climbing, podcasts on psychology, and photography walks. Looking for honesty and shared hobbies.",
        "ig": "Boulder problems #climbing. Street photography. Podcast recs. Sunrise trail photos.",
    },
    {
        "name": "Quinn Patel",
        "slug": "quinn-patel-demo",
        "li": "Data scientist. Interested in chess, trail running, and science museums. Prefer partners who enjoy curiosity-driven plans.",
        "ig": "5K training #running. Chess clocks. Museum tickets. Graphs doodled in notebooks.",
    },
    {
        "name": "Reese Alvarez",
        "slug": "reese-alvarez-demo",
        "li": "Nonprofit program manager. Enjoys community theater, cooking for friends, and city bike advocacy. Looking for warmth and shared values around community.",
        "ig": "Rehearsal selfies #theater. Potluck tables. Bike lane rides. Neighborhood murals.",
    },
    {
        "name": "Harper Singh",
        "slug": "harper-singh-demo",
        "li": "Architect. Passionate about sustainable materials, sketching cities, and ceramics. Prefer creative partners who enjoy quiet studios and galleries.",
        "ig": "Clay wheel days #ceramics. Building sketches. Gallery openings. Material samples.",
    },
    {
        "name": "Drew Kim",
        "slug": "drew-kim-demo",
        "li": "Nurse educator. Interested in yoga, baking bread, and hiking. Looking for balanced weekends and clear communication.",
        "ig": "Sunrise yoga #yoga. Sourdough crumbs #baking. Forest paths. Tea after shifts.",
    },
    {
        "name": "Parker James",
        "slug": "parker-james-demo",
        "li": "Environmental lawyer. Enjoys kayaking, documentary nights, and debate club alumni events. Prefer intellectually curious partners.",
        "ig": "Kayak launches #kayaking. Film stills. Lake mornings. Briefcase beside paddle.",
    },
    {
        "name": "Casey Ortega",
        "slug": "casey-ortega-demo",
        "li": "Mobile eng at civic tech. Interested in soccer, open mic poetry, and thrift shopping. Looking for playful energy and kindness.",
        "ig": "Pickup soccer #soccer. Open mic nights. Thrift finds. City night walks.",
    },
    {
        "name": "Alex Monroe",
        "slug": "alex-monroe-demo",
        "li": "Marine biologist. Passionate about scuba, coastal ecology education, and photography. Prefer partners who enjoy travel and water.",
        "ig": "Dive logs #scuba. Tide pools. Underwater photos. Field notebooks.",
    },
    {
        "name": "Jamie Torres",
        "slug": "jamie-torres-demo",
        "li": "High school history teacher. Enjoys museums, board games, and baking. Looking for someone who likes thoughtful debate and cozy nights.",
        "ig": "Museum tickets #history. Board game stacks. Cookie trays #baking. Classroom plants.",
    },
    {
        "name": "Cameron Lee",
        "slug": "cameron-lee-demo",
        "li": "Fintech PM. Interested in rock climbing, espresso, and weekend farmers markets. Prefer partners who value ambition and rest equally.",
        "ig": "Climbing gym #climbing. Espresso shots. Market flowers #farmersmarket. Skyline runs.",
    },
    {
        "name": "Skyler Amin",
        "slug": "skyler-amin-demo",
        "li": "Documentary filmmaker. Passionate about storytelling, hiking, and vinyl. Looking for creative collaboration and honesty.",
        "ig": "Film stills #filmmaking. Mountain ridges #hiking. Record crates #jazz. Script drafts.",
    },
    {
        "name": "Emery Walsh",
        "slug": "emery-walsh-demo",
        "li": "Landscape photographer. Enjoys camping, stargazing, and coffee roasting. Prefer slow travel and outdoor dates.",
        "ig": "Golden hour frames #photography. Tent under stars. Fresh roast notes. Trail maps.",
    },
    {
        "name": "Logan Park",
        "slug": "logan-park-demo",
        "li": "Robotics engineer. Interested in maker spaces, climbing, and sci-fi novels. Looking for curiosity and humor.",
        "ig": "CNC projects #makerspace. Climbing chalk #climbing. Paperback stacks. Robot arms.",
    },
    {
        "name": "Blake Foster",
        "slug": "blake-foster-demo",
        "li": "Sommelier-in-training and hospitality lead. Enjoys wine education, cooking classes, and jazz nights. Prefer social dinners and travel.",
        "ig": "Tasting notes #wine. Kitchen experiments. Jazz club tables #jazz. Travel plates.",
    },
    {
        "name": "Dakota Ruiz",
        "slug": "dakota-ruiz-demo",
        "li": "Urban planner. Interested in cycling advocacy, community gardens, and sketching streets. Looking for civic-minded partners.",
        "ig": "Bike commute #cycling. Garden plots #gardening. Street sketches. Transit maps.",
    },
    {
        "name": "Phoenix Grant",
        "slug": "phoenix-grant-demo",
        "li": "Sports physiotherapist. Enjoys trail running, strength training, and cooking high-protein meals. Prefer active partners and recovery balance.",
        "ig": "Trail miles #running. Mobility drills. Meal prep boards. Lake cool-downs.",
    },
    {
        "name": "Rowan Hale",
        "slug": "rowan-hale-demo",
        "li": "Librarian and poetry organizer. Interested in book clubs, ceramics, and quiet cafes. Looking for gentle conversation and shared reading.",
        "ig": "Book stacks #reading. Clay bowls #ceramics. Cafe corners. Poem drafts.",
    },
    {
        "name": "Sawyer Nguyen",
        "slug": "sawyer-nguyen-demo",
        "li": "Indie game developer. Enjoys game jams, pixel art, and board cafes. Prefer creative partners who enjoy playful challenges.",
        "ig": "Game jam desks #gamedev. Pixel sketches. Board cafe nights. Controller shelves.",
    },
    {
        "name": "Finley Brooks",
        "slug": "finley-brooks-demo",
        "li": "Sustainability consultant. Interested in sailing, zero-waste cooking, and hiking. Looking for partners who enjoy outdoors and learning.",
        "ig": "Harbor sails #sailing. Zero-waste kitchen. Ridge hikes #hiking. Reusable kits.",
    },
]


SHOWCASE_PAIR_INDEXES = [(0, 1), (0, 6), (3, 19), (4, 24), (7, 21)]


def _stable_float(seed: str, lo: float, hi: float) -> float:
    h = int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16)
    return lo + (h % 10_000) / 10_000 * (hi - lo)


def _rich_transcript(a: Participant, b: Participant, session_id: int) -> list[dict]:
    topics = [
        ("hiking", "weekend outdoors"),
        ("cooking", "shared meals"),
        ("music", "live shows"),
        ("curiosity", "learning together"),
    ]
    messages = []
    for turn in range(6):
        speaker = a if turn % 2 == 0 else b
        peer = b if turn % 2 == 0 else a
        topic, angle = topics[turn % len(topics)]
        if turn == 0:
            text = (
                f"Hi — representing {speaker.display_name}. Their profile evidences interest in {topic}. "
                f"I'd like to learn what {peer.display_name}'s person enjoys on a free Saturday."
            )
            intent = "open"
            q = f"How does {topic} show up in their life?"
        elif turn == 5:
            text = (
                f"Closing for {speaker.display_name}: the exchange suggested possible alignment on {angle}, "
                "with remaining uncertainty about weekly rhythm and long-term preferences."
            )
            intent = "close"
            q = ""
        else:
            text = (
                f"For {speaker.display_name}, {topic} is evidence-supported. "
                f"Reacting to the prior point about {angle}: that resonates if schedules allow. "
                "I won't invent details that aren't in the profile."
            )
            intent = "learn_preferences" if turn % 2 else "share_interest"
            q = f"What does a restorative weeknight look like regarding {angle}?"
        messages.append(
            {
                "speaker_participant_id": speaker.id,
                "turn_index": turn,
                "message": text,
                "question": q,
                "referenced_interests": [topic],
                "intent": intent,
                "confidence": 0.62,
                "is_live_llm": False,
                "model_name": "demo-replay-v1",
            }
        )
    return messages


def seed_demo(*, reset: bool = True) -> int:
    ensure_schema(engine)
    db = SessionLocal()
    try:
        existing = (
            db.query(DemoRun)
            .filter(DemoRun.name == DEMO_RUN_NAME, DemoRun.mode == "demo")
            .order_by(DemoRun.id.desc())
            .first()
        )
        if existing and not reset:
            return existing.id

        if reset:
            # Remove prior synthetic demo data only
            old_runs = db.query(DemoRun).filter(DemoRun.mode == "demo").all()
            for r in old_runs:
                db.delete(r)
            synth = db.query(Participant).filter(Participant.is_synthetic.is_(True)).all()
            for p in synth:
                db.delete(p)
            db.commit()

        participants: list[Participant] = []
        analyses: dict[int, ProfileAnalysis] = {}

        for persona in PERSONAS:
            p = Participant(
                display_name=persona["name"],
                linkedin_url=f"https://www.linkedin.com/in/{persona['slug']}",
                instagram_url=f"https://www.instagram.com/{persona['slug'].replace('-', '')}",
                source_verification_status="synthetic_unverified",
                consent_status="granted",
                adult_eligibility_confirmed=True,
                is_synthetic=True,
            )
            db.add(p)
            db.flush()

            now = datetime.now(timezone.utc)
            li_text = (
                f"[SYNTHETIC DEMO PROFILE — NOT A REAL PERSON]\n"
                f"Name: {persona['name']}\n{persona['li']}"
            )
            ig_text = (
                f"[SYNTHETIC DEMO PROFILE — NOT A REAL PERSON]\n"
                f"@{persona['slug']}\n{persona['ig']}"
            )
            db.add(
                SourceRecord(
                    participant_id=p.id,
                    source_type="linkedin",
                    submitted_url=p.linkedin_url,
                    acquisition_method="demo_seed",
                    permitted_content=li_text,
                    acquisition_status="participant_provided",
                    fetched_at=now,
                    verification_notes="Synthetic demonstration content. Not a verified real profile.",
                )
            )
            db.add(
                SourceRecord(
                    participant_id=p.id,
                    source_type="instagram",
                    submitted_url=p.instagram_url,
                    acquisition_method="demo_seed",
                    permitted_content=ig_text,
                    acquisition_status="participant_provided",
                    fetched_at=now,
                    verification_notes="Synthetic demonstration content. Not a verified real profile.",
                )
            )

            result = deterministic_analysis(li_text, ig_text, persona["name"])
            analysis = ProfileAnalysis(
                participant_id=p.id,
                headline=result["headline"],
                summary=result["summary"],
                needs=result["needs"],
                interests=result["interests"],
                hobbies=result["hobbies"],
                core_values=result["values"],
                personality_traits=result["personality_traits"],
                ideal_date=result["ideal_date"],
                explicitly_stated_preferences=result["explicit_preferences"],
                communication_clues=result["communication_clues"],
                lifestyle_clues=result["lifestyle_clues"],
                relationship_preferences=result["relationship_preferences"],
                evidence_items=result["interests"] + result["hobbies"],
                uncertainty_notes=result["uncertainties"]
                + ["SYNTHETIC DEMO: not a real person."],
                confidence_by_attribute=result["confidence_by_attribute"],
                source_coverage=result["source_coverage"],
                contradictions=result["contradictions"],
                missing_information=result["missing_information"],
                model_name="deterministic-v2",
                prompt_version="v2",
                status="completed",
                is_demo=True,
            )
            db.add(analysis)
            db.flush()
            participants.append(p)
            analyses[p.id] = analysis

        run = DemoRun(
            name=DEMO_RUN_NAME,
            mode="demo",
            status="completed",
            participant_count=len(participants),
            session_count=0,
            completed_sessions=0,
            progress=100.0,
            error_summary="",
            max_turns=6,
            config={"synthetic": True, "label": "DEMO — synthetic cohort"},
            completed_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.flush()

        ids = [p.id for p in participants]
        pairs = unique_pairs(ids)
        assert len(pairs) == 300, f"Expected 300 pairs, got {len(pairs)}"

        id_to_p = {p.id: p for p in participants}
        showcase_id_pairs = {
            (ids[i], ids[j]) if ids[i] < ids[j] else (ids[j], ids[i])
            for i, j in SHOWCASE_PAIR_INDEXES
        }

        for a_id, b_id in pairs:
            a = id_to_p[a_id]
            b = id_to_p[b_id]
            pa = analyses[a_id]
            pb = analyses[b_id]
            # Synthetic mutual evals grounded in analyses
            eval_a = {
                "overall_impression": f"Demo evaluation for {a.display_name}",
                "shared_interests": [],
                "potential_friction": ["Demo uncertainty about weekly schedules"],
                "unanswered_questions": list(pa.missing_information or [])[:3],
                "compatibility_estimate": _stable_float(f"{a_id}-{b_id}-a", 45, 85),
                "confidence": _stable_float(f"{a_id}-{b_id}-ac", 0.4, 0.75),
                "reasoning": "Deterministic demo evaluation from profile overlap.",
            }
            eval_b = {
                "overall_impression": f"Demo evaluation for {b.display_name}",
                "shared_interests": [],
                "potential_friction": ["Demo uncertainty about communication style"],
                "unanswered_questions": list(pb.missing_information or [])[:3],
                "compatibility_estimate": _stable_float(f"{a_id}-{b_id}-b", 45, 85),
                "confidence": _stable_float(f"{a_id}-{b_id}-bc", 0.4, 0.75),
                "reasoning": "Deterministic demo evaluation from profile overlap.",
            }
            scored = compute_session_scores(
                analysis_a=public_analysis_view(pa),
                analysis_b=public_analysis_view(pb),
                eval_a=eval_a,
                eval_b=eval_b,
                transcript=[{"x": 1}] * 6,
            )
            # Keep demo eval shared interests in sync
            eval_a["shared_interests"] = scored["shared_interests"][:5]
            eval_b["shared_interests"] = scored["shared_interests"][:5]

            session = DateSession(
                participant_a_id=a_id,
                participant_b_id=b_id,
                run_id=run.id,
                status="completed",
                current_turn=6,
                max_turns=6,
                date_summary=scored["date_summary"],
                shared_interests=scored["shared_interests"],
                potential_friction=scored["potential_friction"],
                unanswered_questions=scored["unanswered_questions"],
                agent_a_feedback=eval_a,
                agent_b_feedback=eval_b,
                compatibility_score=scored["compatibility_score"],
                confidence=scored["confidence"],
                score_breakdown=scored["score_breakdown"],
                is_demo_replay=True,
                completed_at=datetime.now(timezone.utc),
            )
            db.add(session)
            db.flush()

            if (a_id, b_id) in showcase_id_pairs:
                for m in _rich_transcript(a, b, session.id):
                    db.add(DateMessage(session_id=session.id, **m))
            else:
                # Minimal persisted exchange for all pairs (still multi-turn, contextual stubs)
                for turn in range(4):
                    speaker = a if turn % 2 == 0 else b
                    peer = b if turn % 2 == 0 else a
                    db.add(
                        DateMessage(
                            session_id=session.id,
                            speaker_participant_id=speaker.id,
                            turn_index=turn,
                            message=(
                                f"[DEMO REPLAY] {speaker.display_name}'s agent discusses "
                                f"evidence-backed interests with {peer.display_name}'s agent (turn {turn+1})."
                            ),
                            question="What remains uncertain about lifestyle fit?",
                            referenced_interests=(scored["shared_interests"][:1] or ["curiosity"]),
                            intent="open" if turn == 0 else ("close" if turn == 3 else "learn_preferences"),
                            confidence=0.5,
                            is_live_llm=False,
                            model_name="demo-replay-v1",
                        )
                    )

        run.session_count = 300
        run.completed_sessions = 300
        db.commit()

        aggregate_rankings(db, run.id)

        # Verify ranking completeness: 25 * 24 = 600
        rank_count = db.query(Ranking).filter(Ranking.run_id == run.id).count()
        assert rank_count == 600, f"Expected 600 rankings, got {rank_count}"

        print(f"Seeded demo run id={run.id} with {len(participants)} synthetic participants, 300 sessions, {rank_count} rankings.")
        return run.id
    finally:
        db.close()


def main() -> None:
    seed_demo(reset=True)


if __name__ == "__main__":
    main()
