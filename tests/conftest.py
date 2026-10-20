"""Test fixtures. Boots the bundled mock-platform server as a real subprocess
on a free port (connectors make real HTTP calls, so this is closer to the
real integration than mocking httpx), points DISCOURSE/DEVTO/WEBHOOK base
URLs at it, and gives every test a clean sqlite DB. No API keys needed --
SIMULATION_MODE is forced true before any app module is imported.
"""
import os
import socket
import subprocess
import sys
import time

import httpx
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# This module is imported by pytest before any test module, so these env
# vars are in place before app.core.config.settings (a module-level
# singleton) is instantiated by anyone's first `import app...`. Setting
# them later, inside a fixture, is too late -- collection already imported
# the app.
os.environ["SIMULATION_MODE"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///./data/test_incubrix.db"
os.environ["INCUBRIX_FORCE_LOCAL_STORAGE"] = "1"
os.environ["INCUBRIX_DISABLE_SCHEDULER"] = "1"
os.environ.setdefault("WEBHOOK_SHARED_SECRET", "dev_only_shared_secret_change_me")
if os.path.exists(os.path.join(ROOT, "data", "test_incubrix.db")):
    os.remove(os.path.join(ROOT, "data", "test_incubrix.db"))


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="session", autouse=True)
def mock_platform_server():
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"

    # NOTE: these three only affect code that reads them fresh via
    # app.core.config.settings (already-constructed at import time, but its
    # fields were set from os.environ at that point -- these three were not
    # yet known then, so patch the already-built settings object directly.
    from app.core.config import settings as _settings
    _settings.DISCOURSE_MOCK_BASE_URL = base_url
    _settings.DEVTO_MOCK_BASE_URL = base_url
    _settings.WEBHOOK_RECEIVER_BASE_URL = base_url
    os.environ["DISCOURSE_MOCK_BASE_URL"] = base_url
    os.environ["DEVTO_MOCK_BASE_URL"] = base_url
    os.environ["WEBHOOK_RECEIVER_BASE_URL"] = base_url

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "mocks.platform_mock.main:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT, env=os.environ.copy(),
    )
    for _ in range(50):
        try:
            httpx.get(f"{base_url}/health", timeout=0.5)
            break
        except Exception:
            time.sleep(0.2)
    else:
        proc.terminate()
        raise RuntimeError("mock platform server did not start")

    yield base_url

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture()
def client(mock_platform_server):
    from fastapi.testclient import TestClient
    from app.core.db import init_db, Base, engine
    Base.metadata.drop_all(bind=engine)
    init_db()
    from app.main import app
    return TestClient(app)


@pytest.fixture()
def db_session():
    from app.core.db import SessionLocal, init_db, Base, engine
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    yield db
    db.close()
