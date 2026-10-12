import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["LLM_API_KEY"] = ""
os.environ["LLM_PROVIDER"] = "none"
os.environ["FRONTEND_ORIGIN"] = "http://localhost:5173"
# Tests never touch LinkedIn/Instagram or a saved snapshot.
os.environ["SCRAPING_ENABLED"] = "false"
os.environ["APIFY_TOKEN"] = ""
os.environ["DEMO_SNAPSHOT_PATH"] = "does-not-exist.json"

from app.core.config import get_settings

get_settings.cache_clear()

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db: Session, monkeypatch) -> Generator[TestClient, None, None]:
    app = create_app()
    # Background dating runs open their own sessions; point them at the test database.
    from app.db import session as session_mod

    monkeypatch.setattr(
        session_mod,
        "SessionLocal",
        sessionmaker(bind=db.get_bind(), autoflush=False, autocommit=False),
    )

    def _override() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
