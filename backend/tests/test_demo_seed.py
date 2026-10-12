from app.models import DateSession, Participant, Ranking
from app.seed_demo import seed_demo


def test_demo_seed_idempotent_and_complete(db, monkeypatch):
    # Point seed at the test DB session's engine by patching SessionLocal
    from app.db import session as session_mod
    from sqlalchemy.orm import sessionmaker

    TestingSession = sessionmaker(bind=db.get_bind(), autoflush=False, autocommit=False)
    monkeypatch.setattr(session_mod, "SessionLocal", TestingSession)
    monkeypatch.setattr("app.seed_demo.SessionLocal", TestingSession)
    monkeypatch.setattr("app.seed_demo.engine", db.get_bind())

    run_id_1 = seed_demo(reset=True)
    run_id_2 = seed_demo(reset=True)
    assert run_id_2 >= run_id_1

    fresh = TestingSession()
    try:
        synth = fresh.query(Participant).filter(Participant.is_synthetic.is_(True)).count()
        assert synth == 25
        sessions = fresh.query(DateSession).filter(DateSession.run_id == run_id_2).count()
        assert sessions == 300
        rankings = fresh.query(Ranking).filter(Ranking.run_id == run_id_2).count()
        assert rankings == 600

        # Each participant has 24 candidates
        from app.models import Ranking as R

        pid = fresh.query(Participant).filter(Participant.is_synthetic.is_(True)).first().id
        assert fresh.query(R).filter(R.run_id == run_id_2, R.participant_id == pid).count() == 24
        # No self ranks
        assert (
            fresh.query(R)
            .filter(R.run_id == run_id_2, R.participant_id == R.candidate_id)
            .count()
            == 0
        )
    finally:
        fresh.close()
