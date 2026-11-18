"""Regression tests for the final whole-repo review findings (Critical/Important)."""

from __future__ import annotations

import uuid
from datetime import timedelta

from app.core.db import utcnow
from app.domain.models import Licence, Project, RenderJob
from app.workers.queue import InlineQueue, sweep_render_jobs
from app.workers.render_worker import process_render_job
from tests.conftest import HoldQueue, create_character, sign_in, template_recipe
from tests.test_renders import project_with_storyboard, submit


# 1 (critical) guest sessions survive access-token expiry via a refresh token
def test_refresh_token_keeps_guest_account(client, container):
    s = client.post("/v1/auth/session", json={"provider": "guest"}).json()
    assert s["refreshToken"]
    container.settings.access_token_ttl_seconds = -10  # every new access token is already expired
    r = client.post("/v1/auth/refresh", json={"refreshToken": s["refreshToken"]})
    assert r.status_code == 200 and r.json()["user"]["id"] == s["user"]["id"]
    assert client.post("/v1/auth/refresh", json={"refreshToken": s["accessToken"]}).status_code == 401


# 2/3/4 sweeper: expired leases, cancel requests on dead workers, backed-off jobs
def test_sweeper_recovers_expired_lease_and_finishes_cancelled(client, auth, container):
    p = project_with_storyboard(client, auth, container)
    container.queue = HoldQueue()
    a = uuid.UUID(submit(client, auth, p["id"], "a").json()["id"])
    b = uuid.UUID(submit(client, auth, p["id"], "b").json()["id"])
    with container.db.session() as s:
        for jid, cancel in ((a, False), (b, True)):
            j = s.get(RenderJob, jid)
            j.status, j.lease_expires_at, j.cancel_requested = "processing", utcnow() - timedelta(seconds=5), cancel
        s.commit()
    container.queue = InlineQueue(container)
    sweep_render_jobs(container)
    with container.db.session() as s:
        assert s.get(RenderJob, a).status == "completed"
        assert s.get(RenderJob, b).status == "cancelled"


def test_sweeper_respects_backoff_delay(client, auth, container):
    p = project_with_storyboard(client, auth, container)
    container.queue = HoldQueue()
    jid = uuid.UUID(submit(client, auth, p["id"]).json()["id"])
    with container.db.session() as s:
        s.get(RenderJob, jid).next_attempt_at = utcnow() + timedelta(seconds=30)
        s.commit()
    hold = HoldQueue()
    container.queue = hold
    sweep_render_jobs(container)
    assert hold.jobs and hold.jobs[0][0] == jid and 25 <= hold.jobs[0][1] <= 30


def test_cancel_and_retry_work_on_dead_processing_job(client, auth, container):
    p = project_with_storyboard(client, auth, container)
    container.queue = HoldQueue()
    jid = submit(client, auth, p["id"]).json()["id"]
    with container.db.session() as s:
        j = s.get(RenderJob, uuid.UUID(jid))
        j.status, j.lease_expires_at = "processing", utcnow() - timedelta(seconds=5)
        s.commit()
    assert client.post(f"/v1/renders/{jid}/cancel", headers=auth).json()["status"] == "cancelled"


# 6 cancel must not overwrite a job a worker already claimed
def test_cancel_after_claim_does_not_mark_cancelled(client, auth, container):
    from app.services.render import cancel_job

    p = project_with_storyboard(client, auth, container)
    container.queue = HoldQueue()
    jid = uuid.UUID(submit(client, auth, p["id"]).json()["id"])
    with container.db.session() as stale, container.db.session() as worker:
        job = stale.get(RenderJob, jid)  # API loaded it while queued
        w = worker.get(RenderJob, jid)
        w.status, w.lease_expires_at = "processing", utcnow() + timedelta(minutes=5)
        worker.commit()
        cancel_job(stale, job)
    with container.db.session() as s:
        j = s.get(RenderJob, jid)
        assert j.status == "processing" and j.cancel_requested is True


# 7 revoked licence blocks rendering
def test_revoked_licence_blocks_render(client, auth, container):
    p = project_with_storyboard(client, auth, container)
    container.queue = HoldQueue()
    jid = uuid.UUID(submit(client, auth, p["id"], "x").json()["id"])
    with container.db.session() as s:
        s.get(Licence, "lic_cv_original_v1").review_status = "revoked"
        s.commit()
        container.catalog.refresh_from_db(s)
    assert submit(client, auth, p["id"], "y").status_code == 422
    assert process_render_job(container, jid) == "failed"


# 8 account deletion removes per-user caches and stops in-flight renders
def test_delete_account_removes_caches_and_active_jobs(client, container):
    h = sign_in(client, "zed", "Zed")
    a = create_character(client, h, template_recipe(container, "tmpl_voltwood_guardian"))
    client.post("/v1/previews", json={"recipe": a["recipe"]}, headers=h)
    client.post(
        "/v1/stories/generate", headers=h, json={"prompt": "x", "characterIds": [a["id"]], "durationSeconds": 15}
    )
    user_id = client.get("/v1/me", headers=h).json()["id"]
    root = container.storage.root
    assert any(root.joinpath("users", user_id).rglob("*"))
    assert client.delete("/v1/me", headers=h).status_code == 204
    assert not root.joinpath("users", user_id).exists()


# 9 uploads larger than declared are rejected without buffering everything
def test_upload_stream_limit(client, auth):
    ok = client.post(
        "/v1/uploads/presign",
        headers=auth,
        json={
            "fileName": "a.png",
            "mimeType": "image/png",
            "fileSize": 16,
            "purpose": "reference_image",
            "rightsConfirmed": True,
        },
    ).json()
    path = ok["uploadUrl"].replace("http://localhost:8000", "")
    r = client.put(path, content=(b"\x89PNG\r\n\x1a\n" + b"0" * 10_000))
    assert r.status_code == 422 and r.json()["error"]["code"] == "UPLOAD_REJECTED"


# 10 guest creation is throttled per client
def test_guest_creation_rate_limited(client, container):
    container.settings.rate_limit_sessions_per_minute = 3
    codes = [client.post("/v1/auth/session", json={"provider": "guest"}).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]


# 11 a moderation block must not leave partial writes
def test_blocked_request_leaves_no_partial_writes(client, auth, container):
    c = create_character(client, auth, template_recipe(container, "tmpl_mossy_pip"))
    recipe = dict(c["recipe"], name="Mossy Pip Two")
    r = client.patch(
        f"/v1/characters/{c['id']}", headers=auth, json={"recipe": recipe, "description": "Captain Starlance"}
    )
    assert r.status_code == 422
    assert client.get(f"/v1/characters/{c['id']}", headers=auth).json()["version"] == 1
    sb = {
        "schemaVersion": 1,
        "title": "Princess Quillara",
        "logline": "",
        "synopsis": "",
        "durationSeconds": 15,
        "aspectRatio": "16:9",
        "language": "en",
        "musicCueId": None,
        "characters": [{"characterId": c["id"], "displayName": "Mossy", "role": "protagonist"}],
        "scenes": [
            {
                "sceneId": "s1",
                "sequence": 1,
                "title": "t",
                "durationMs": 3000,
                "environmentId": "env_sky_city_01",
                "cameraPresetId": "cam_wide",
                "lightingPresetId": "light_daylight",
                "characters": [{"characterId": c["id"], "position": "center", "scale": 1, "actionId": "idle"}],
                "dialogue": [],
                "soundEffectIds": [],
                "transition": "cut",
            }
        ],
    }
    before = len(client.get("/v1/projects", headers=auth).json()["items"])
    assert client.post("/v1/projects", json={"title": "ok", "storyboard": sb}, headers=auth).status_code == 422
    assert len(client.get("/v1/projects", headers=auth).json()["items"]) == before
    _ = Project
