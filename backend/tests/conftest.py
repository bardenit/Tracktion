import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

IMPORT_DATA_DIR = Path("/tmp/tracktion-tests")
IMPORT_DATA_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("DATA_DIR", str(IMPORT_DATA_DIR))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{IMPORT_DATA_DIR / 'import.db'}")
os.environ.setdefault("DEBUG", "true")


@pytest.fixture
def db_url(tmp_path):
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def db_session(db_url):
    from app.database import Base
    from app import models  # noqa: F401

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def seeded_objects(db_session):
    from app.models import User, Vehicle, VehicleCollaborator

    owner = User(email="owner@example.test", password_hash="hash")
    collaborator = User(email="collaborator@example.test", password_hash="hash")
    vehicle = Vehicle(user_id=1, make="Honda", model="Civic", year=2020)
    db_session.add_all([owner, collaborator])
    db_session.flush()
    vehicle.user_id = owner.id
    db_session.add(vehicle)
    db_session.flush()
    db_session.add(VehicleCollaborator(vehicle_id=vehicle.id, user_id=collaborator.id, role="viewer"))
    db_session.commit()
    return owner, collaborator, vehicle


@pytest.fixture
def app_client(db_session, seeded_objects):
    from app.auth import get_current_user
    from app.database import get_db
    from app.main import app
    from app.migrations import upgrade_database

    owner, _, _ = seeded_objects
    upgrade_database(os.environ["DATABASE_URL"])

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: owner
    app.state.database_ready = True
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
