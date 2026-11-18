"""Seed a deterministic demo account (characters, a fusion, a storyboard project and renders).

  CV_DATABASE_URL=... python -m scripts.seed_demo [--render]

Prints a dev access token for the demo user so the mobile apps / curl can use it.
"""

from __future__ import annotations

import sys

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def main() -> None:
    settings = get_settings()
    settings.queue_backend = "inline" if "--render" in sys.argv else settings.queue_backend
    app = create_app(settings)
    c = TestClient(app)
    s = c.post("/v1/auth/session", json={"provider": "dev", "token": "demo", "displayName": "Demo Creator"}).json()
    h = {"Authorization": f"Bearer {s['accessToken']}"}
    if c.get("/v1/characters", headers=h).json()["items"]:
        print("demo data already present")
        print(f"DEMO_TOKEN={s['accessToken']}")
        return
    cat = app.state.container.catalog
    ids = {}
    for tid in ("tmpl_voltwood_guardian", "tmpl_nova_sprocket", "tmpl_mossy_pip", "tmpl_zibba", "tmpl_ember_ridgeback"):
        ids[tid] = c.post("/v1/characters", json={"recipe": cat.get(tid).data["recipe"]}, headers=h).json()["id"]
    c.patch(f"/v1/characters/{ids['tmpl_voltwood_guardian']}", json={"isFavorite": True}, headers=h)
    c.post(
        "/v1/mixes",
        headers=h,
        json={
            "sourceCharacterIds": [ids["tmpl_voltwood_guardian"], ids["tmpl_zibba"]],
            "dimensions": ["appearance", "powers"],
        },
    )
    story = c.post(
        "/v1/stories/generate",
        headers=h,
        json={
            "prompt": "find the glowing map in the crystal forest",
            "tone": "playful",
            "durationSeconds": 15,
            "characterIds": [ids["tmpl_voltwood_guardian"], ids["tmpl_mossy_pip"]],
        },
    ).json()["storyboard"]
    p = c.post("/v1/projects", headers=h, json={"title": story["title"], "storyboard": story}).json()
    if "--render" in sys.argv:
        job = c.post(
            f"/v1/projects/{p['id']}/renders",
            json={"quality": "draft"},
            headers={**h, "Idempotency-Key": "demo-render-1"},
        ).json()
        print("render:", c.get(f"/v1/renders/{job['id']}", headers=h).json()["status"])
    print(f"DEMO_TOKEN={s['accessToken']}")


if __name__ == "__main__":
    main()
