"""Record real API responses into shared/fixtures/api/ for iOS/Android DTO decoding tests.

IDs/timestamps vary per run, so these are refreshed deliberately (not checked for staleness).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import REPO_ROOT, Settings
from app.main import create_app

OUT = REPO_ROOT / "shared" / "fixtures" / "api"


class _FastRenderer:
    name = "sample"

    def render(self, plan, work, cancel_check, progress):
        work.mkdir(parents=True, exist_ok=True)
        (work / "o.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
        (work / "t.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        return work / "o.mp4", work / "t.png", sum(s["durationMs"] for s in plan.storyboard["scenes"])


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(
            env="test",
            database_url=f"sqlite:///{tmp}/a.db",
            storage_dir=Path(tmp) / "s",
            work_dir=Path(tmp) / "w",
            queue_backend="inline",
        )
        app = create_app(settings)
        app.state.container.extras["renderer_factory"] = _FastRenderer
        c = TestClient(app)
        save = lambda name, data: (OUT / f"{name}.json").write_text(json.dumps(data, indent=2) + "\n")  # noqa: E731
        session = c.post("/v1/auth/session", json={"provider": "dev", "token": "sample", "displayName": "Sam"}).json()
        save("session", session)
        h = {"Authorization": f"Bearer {session['accessToken']}"}
        cat = app.state.container.catalog
        a = c.post(
            "/v1/characters", json={"recipe": cat.get("tmpl_voltwood_guardian").data["recipe"]}, headers=h
        ).json()
        b = c.post("/v1/characters", json={"recipe": cat.get("tmpl_mossy_pip").data["recipe"]}, headers=h).json()
        save("character", a)
        save("character_list", c.get("/v1/characters", headers=h).json())
        save(
            "generate_recipe",
            c.post(
                "/v1/characters/generate-recipe",
                headers=h,
                json={"description": "a tall blue robot with a visor and a shield"},
            ).json(),
        )
        save(
            "mix_preview",
            c.post(
                "/v1/mixes/preview", headers=h, json={"sourceCharacterIds": [a["id"], b["id"]], "dimensions": ["all"]}
            ).json(),
        )
        story = c.post(
            "/v1/stories/generate",
            headers=h,
            json={"prompt": "find the glowing map", "characterIds": [a["id"], b["id"]], "durationSeconds": 15},
        ).json()
        save("story_generate", story)
        project = c.post("/v1/projects", headers=h, json={"title": "Map Day", "storyboard": story["storyboard"]}).json()
        save("project", project)
        job = c.post(
            f"/v1/projects/{project['id']}/renders",
            json={"quality": "draft"},
            headers={**h, "Idempotency-Key": "sample-1"},
        ).json()
        save("render_job", c.get(f"/v1/renders/{job['id']}", headers=h).json())
        save("render_list", c.get("/v1/renders", headers=h).json())
        save("download_url", c.get(f"/v1/renders/{job['id']}/download-url", headers=h).json())
        save("catalog_manifest", c.get("/v1/catalog/manifest").json())
        save(
            "error_recipe_invalid",
            c.post(
                "/v1/characters",
                headers=h,
                json={"recipe": {**cat.get("tmpl_voltwood_guardian").data["recipe"], "modules": ["spike_tail_01"]}},
            ).json(),
        )
        save("usage", c.get("/v1/me/usage", headers=h).json())
    print(f"wrote samples to {OUT}")


if __name__ == "__main__":
    main()
