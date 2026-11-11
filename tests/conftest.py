"""Test fixtures for Linkly.

Each test gets a fresh, isolated in-memory SQLite database so tests
never touch the real ``linkly.db`` file.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def engine():
    """A fresh in-memory SQLite engine for one test."""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture()
def db_session(engine):
    """A raw SQLAlchemy session on the test database."""
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    yield db
    db.close()


@pytest.fixture()
def client(engine):
    """A TestClient whose database dependency points at the test database."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # Plain TestClient (no context manager) so the app's lifespan does not
    # create tables on the real production database during tests.
    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client
    app.dependency_overrides.clear()
