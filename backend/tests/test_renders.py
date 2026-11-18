from __future__ import annotations

import uuid
from datetime import timedelta

from app.core.db import utcnow
from app.domain.models import RenderJob
from app.workers.queue import InlineQueue, recover_stranded_jobs
from app.workers.render_worker import process_render_job
from tests.conftest import FakeRenderer, HoldQueue, create_character, template_recipe


def project_with_storyboard(client, auth, container, seconds=15):
    a = create_character(client, auth, template_recipe(container, "tmpl_voltwood_guardian"))
    b = create_character(client, auth, template_recipe(container, "tmpl_nova_sprocket"))
    sb = client.post(
        "/v1/stories/generate",
        headers=auth,
        json={
            "prompt": "race across the sky city",
            "characterIds": [a["id"], b["id"]],
            "durationSeconds": seconds,
        },
    ).json()["storyboard"]
    return client.post("/v1/projects", json={"title": "Sky Race", "storyboard": sb}, headers=auth).json()


def submit(client, auth, pid, key="k1", **body):
    return client.post(f"/v1/projects/{pid}/renders", json=body, headers={**auth, "Idempotency-Key": key})


def test_render_completes_with_download_url(client, auth, container):
    p = project_with_storyboard(client, auth, container)
    r = submit(client, auth, p["id"])
    assert r.status_code == 201, r.text
    job = client.get(f"/v1/renders/{r.json()['id']}", headers=auth).json()
    assert job["status"] == "completed" and job["progressStage"] == "completed" and job["progressPercent"] == 100
    assert job["durationMs"] == 15000 and job["width"] == 854
    dl = client.get(f"/v1/renders/{job['id']}/download-url", headers=auth).json()
    assert client.get(dl["url"].replace("http://localhost:8000", "")).status_code == 200
    assert client.get("/v1/renders", headers=auth).json()["items"][0]["projectTitle"] == "Sky Race"


def test_idempotency_key_replay_and_conflict(client, auth, container):
    p = project_with_storyboard(client, auth, container)
    first = submit(client, auth, p["id"], "same")
    replay = submit(client, auth, p["id"], "same")
    assert replay.status_code == 200 and replay.json()["id"] == first.json()["id"]
    conflict = submit(client, auth, p["id"], "same", quality="final")
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert container.extras["fake_renderer"].calls == 1


def test_duplicate_delivery_is_harmless(client, auth, container):
    p = project_with_storyboard(client, auth, container)
    job_id = uuid.UUID(submit(client, auth, p["id"]).json()["id"])
    assert process_render_job(container, job_id) == "completed"  # second delivery: no re-render
    assert container.extras["fake_renderer"].calls == 1


def test_transient_failures_retry_with_backoff_then_succeed(client, auth, container):
    container.extras["fake_renderer"] = FakeRenderer(["transient", "transient", "ok"])
    p = project_with_storyboard(client, auth, container)
    job = submit(client, auth, p["id"]).json()
    job = client.get(f"/v1/renders/{job['id']}", headers=auth).json()
    assert job["status"] == "completed" and job["attempts"] == 3


def test_retries_are_bounded(client, auth, container):
    container.extras["fake_renderer"] = FakeRenderer(["transient"] * 5)
    p = project_with_storyboard(client, auth, container)
    job = client.get(f"/v1/renders/{submit(client, auth, p['id']).json()['id']}", headers=auth).json()
    assert job["status"] == "failed" and job["errorCode"] == "RENDER_RETRIES_EXHAUSTED"
    assert job["attempts"] == container.settings.render_max_attempts
    retried = client.post(f"/v1/renders/{job['id']}/retry", headers=auth).json()
    assert retried["status"] == "completed"


def test_permanent_failure_not_retried(client, auth, container):
    container.extras["fake_renderer"] = FakeRenderer(["permanent"])
    p = project_with_storyboard(client, auth, container)
    job = client.get(f"/v1/renders/{submit(client, auth, p['id']).json()['id']}", headers=auth).json()
    assert job["status"] == "failed" and job["errorCode"] == "STORYBOARD_INVALID" and job["attempts"] == 1


def test_malformed_scene_document_fails_safely(client, auth, container):
    p = project_with_storyboard(client, auth, container)
    container.queue = HoldQueue()  # hold the job in the queue
    job_id = uuid.UUID(submit(client, auth, p["id"]).json()["id"])
    with container.db.session() as s:
        job = s.get(RenderJob, job_id)
        bad = dict(job.settings_json)
        bad["storyboard"] = {**bad["storyboard"], "scenes": [{"sceneId": "x", "evil": "import os"}]}
        job.settings_json = bad
        s.commit()
    assert process_render_job(container, job_id) == "failed"
    with container.db.session() as s:
        assert s.get(RenderJob, job_id).error_code == "STORYBOARD_INVALID"


def test_cancel_queued_and_processing(client, auth, container):
    p = project_with_storyboard(client, auth, container)
    container.queue = HoldQueue()
    queued = submit(client, auth, p["id"], "a").json()
    r = client.post(f"/v1/renders/{queued['id']}/cancel", headers=auth).json()
    assert r["status"] == "cancelled"
    assert process_render_job(container, uuid.UUID(queued["id"])) == "cancelled"
    assert container.extras["fake_renderer"].calls == 0
    again = client.post(f"/v1/renders/{queued['id']}/cancel", headers=auth)
    assert again.status_code == 409

    job2 = submit(client, auth, p["id"], "b").json()
    with container.db.session() as s:  # simulate a running job
        j = s.get(RenderJob, uuid.UUID(job2["id"]))
        j.status, j.lease_expires_at = "processing", utcnow() + timedelta(minutes=5)
        s.commit()
    r = client.post(f"/v1/renders/{job2['id']}/cancel", headers=auth).json()
    assert r["status"] == "processing" and r["cancelRequested"] is True


def test_worker_restart_recovers_expired_lease(client, auth, container):
    p = project_with_storyboard(client, auth, container)
    container.queue = HoldQueue()
    job_id = uuid.UUID(submit(client, auth, p["id"]).json()["id"])
    with container.db.session() as s:  # worker crashed mid-render: lease expired
        j = s.get(RenderJob, job_id)
        j.status, j.attempts, j.lease_expires_at = "processing", 1, utcnow() - timedelta(seconds=1)
        s.commit()
    container.queue = InlineQueue(container)
    assert recover_stranded_jobs(container) == [job_id]
    with container.db.session() as s:
        j = s.get(RenderJob, job_id)
        assert j.status == "completed" and j.attempts == 2


def test_live_lease_is_not_stolen(client, auth, container):
    p = project_with_storyboard(client, auth, container)
    container.queue = HoldQueue()
    job_id = uuid.UUID(submit(client, auth, p["id"]).json()["id"])
    with container.db.session() as s:
        j = s.get(RenderJob, job_id)
        j.status, j.lease_expires_at = "processing", utcnow() + timedelta(minutes=5)
        s.commit()
    assert process_render_job(container, job_id) == "processing"
    assert container.extras["fake_renderer"].calls == 0


def test_active_render_quota(client, auth, container):
    container.settings.max_active_renders_per_user = 1
    p = project_with_storyboard(client, auth, container)
    container.queue = HoldQueue()
    assert submit(client, auth, p["id"], "1").status_code == 201
    r = submit(client, auth, p["id"], "2")
    assert r.status_code == 429 and r.json()["error"]["code"] == "QUOTA_EXCEEDED"


def test_download_before_complete(client, auth, container):
    p = project_with_storyboard(client, auth, container)
    container.queue = HoldQueue()
    job = submit(client, auth, p["id"]).json()
    r = client.get(f"/v1/renders/{job['id']}/download-url", headers=auth)
    assert r.status_code == 409 and r.json()["error"]["code"] == "RENDER_NOT_READY"


def test_idempotency_header_required(client, auth, container):
    p = project_with_storyboard(client, auth, container)
    r = client.post(f"/v1/projects/{p['id']}/renders", json={}, headers=auth)
    assert r.status_code == 422


def test_blender_scene_document_is_data_only(client, auth, container):
    import json

    from app.workers.blender_scene import scene_document
    from app.workers.render_worker import build_plan

    p = project_with_storyboard(client, auth, container)
    container.queue = HoldQueue()
    job_id = uuid.UUID(submit(client, auth, p["id"]).json()["id"])
    with container.db.session() as s:
        plan = build_plan(container, s.get(RenderJob, job_id).settings_json)
    doc = scene_document(plan)
    assert doc["fps"] == 24 and len(doc["scenes"]) == 3
    assert all(isinstance(a["x"], float) for sc in doc["scenes"] for a in sc["actors"])
    assert "import" not in json.dumps(doc)
