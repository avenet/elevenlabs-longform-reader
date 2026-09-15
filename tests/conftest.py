import os
import tempfile
from pathlib import Path

_TEST_DIR = Path(tempfile.mkdtemp(prefix="reader-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DIR / 'test.db'}"
os.environ["MEDIA_ROOT"] = str(_TEST_DIR / "media")
os.environ["ELEVENLABS_API_KEY"] = "test-key"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.services.storage import ensure_storage


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    ensure_storage()
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
