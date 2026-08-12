# tests/conftest.py
"""Fixtures compartilhadas — usa banco temporário isolado por sessão"""
import os
import tempfile

# Deve ser definido ANTES de importar a aplicação (settings é singleton)
_tmp_dir = tempfile.mkdtemp(prefix="radar_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_dir}/test.db"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-at-least-32-bytes-long!"
os.environ["ENV"] = "test"
os.environ["DEBUG"] = "True"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.shared.database import db
from app.shared.security import security


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _init_db():
    await db.init()
    yield
    # Remove o banco temporário
    import glob
    for f in glob.glob(os.path.join(_tmp_dir, "test.db*")):
        os.remove(f)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c