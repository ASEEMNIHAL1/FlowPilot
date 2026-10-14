import pytest
from fastapi.testclient import TestClient

import app.db as db_module
from app.config import get_settings, reset_settings_cache
from app.db import configure_engine, init_db
from app.main import create_app
from app.services.seed import reset_demo_data


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "flowpilot-test.db"
    monkeypatch.setenv("FLOWPILOT_DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("FLOWPILOT_LLM_PROVIDER", "dev")
    monkeypatch.setenv("FLOWPILOT_TIMEZONE", "Asia/Kolkata")
    monkeypatch.setenv("FLOWPILOT_INJECT_CREATE_FAILURES", "0")
    reset_settings_cache()
    settings = get_settings()
    configure_engine(settings.database_url)
    init_db()
    # Always read SessionLocal through the module so we get the updated
    # sessionmaker created by configure_engine(), not the stale import-time copy.
    db = db_module.SessionLocal()
    try:
        reset_demo_data(db, settings)
    finally:
        db.close()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session(client):
    session = db_module.SessionLocal()
    try:
        yield session
    finally:
        session.close()
