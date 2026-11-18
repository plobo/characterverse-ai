from __future__ import annotations

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.container import build_container
from app.main import create_app

FIXTURES = Path(__file__).parent / "fixtures"
logging.getLogger("httpx").setLevel(logging.WARNING)


class FakeRenderer:
    """Fast stand-in for the procedural renderer. Behaviour is scripted per test."""

    name = "fake"

    def __init__(self, script: list[str] | None = None):
        self.script = script or []
        self.calls = 0

    def render(self, plan, work, cancel_check, progress):
        from app.workers.renderer import PermanentRenderError, RenderCancelled, TransientRenderError

        self.calls += 1
        action = self.script.pop(0) if self.script else "ok"
        progress("rendering_scenes", 30)
        if action == "transient":
            raise TransientRenderError("simulated node loss")
        if action == "permanent":
            raise PermanentRenderError("STORYBOARD_INVALID", "simulated malformed scene")
        if action == "cancel" or cancel_check():
            raise RenderCancelled()
        work.mkdir(parents=True, exist_ok=True)
        (work / "o.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42fake")
        (work / "t.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
        return work / "o.mp4", work / "t.png", sum(s["durationMs"] for s in plan.storyboard["scenes"])


class HoldQueue:
    """Accepts jobs without running them (simulates a backed-up queue)."""

    def __init__(self):
        self.jobs = []

    def enqueue(self, job_id, delay: float = 0.0):
        self.jobs.append((job_id, delay))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        env="test",
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        storage_dir=tmp_path / "storage",
        work_dir=tmp_path / "work",
        queue_backend="inline",
        denylist_path=FIXTURES / "test_denylist.txt",
        rate_limit_generate_per_minute=1000,
        render_backoff_base_seconds=0.01,
    )


@pytest.fixture
def container(settings):
    c = build_container(settings)
    c.extras["fake_renderer"] = FakeRenderer()
    c.extras["renderer_factory"] = lambda: c.extras["fake_renderer"]
    return c


@pytest.fixture
def client(settings, container) -> TestClient:
    app = create_app(settings, container)
    with TestClient(app) as tc:
        yield tc


def sign_in(client: TestClient, subject: str = "alice", name: str = "Alice") -> dict[str, str]:
    r = client.post("/v1/auth/session", json={"provider": "dev", "token": subject, "displayName": name})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


@pytest.fixture
def auth(client) -> dict[str, str]:
    return sign_in(client)


def template_recipe(container, template_id: str) -> dict:
    return dict(container.catalog.get(template_id).data["recipe"])


def create_character(client, headers, recipe) -> dict:
    r = client.post("/v1/characters", json={"recipe": recipe}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()
