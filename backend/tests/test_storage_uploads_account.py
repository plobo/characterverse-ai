from __future__ import annotations

import pytest

from app.core.errors import AppError
from app.domain.models import AuditEvent, Character, ModerationEvent, User
from tests.conftest import create_character, sign_in, template_recipe


def test_signed_url_expiry_and_tamper(container):
    st = container.storage
    st.put("previews/x.txt", b"hi")
    url, exp = st.signed_url("previews/x.txt", 60, now=1000)
    sig = url.split("sig=")[1]
    st.verify("previews/x.txt", exp, sig, now=1059)
    with pytest.raises(AppError) as e:
        st.verify("previews/x.txt", exp, sig, now=1061)
    assert e.value.code == "SIGNATURE_EXPIRED"
    with pytest.raises(AppError) as e:
        st.verify("previews/y.txt", exp, sig, now=1000)
    assert e.value.code == "SIGNATURE_INVALID"
    with pytest.raises(AppError):
        st.verify("previews/x.txt", exp, sig, method="PUT", now=1000)


def test_path_traversal_rejected(container):
    with pytest.raises(AppError):
        container.storage.put("../escape.txt", b"x")


def test_expired_media_url_http(client, container):
    container.storage.put("previews/z.txt", b"z")
    url, _ = container.storage.signed_url("previews/z.txt", -5)
    r = client.get(url.replace("http://localhost:8000", ""))
    assert r.status_code == 403 and r.json()["error"]["code"] == "SIGNATURE_EXPIRED"


def test_presigned_upload_validates_type_and_rights(client, auth):
    no_rights = client.post(
        "/v1/uploads/presign",
        headers=auth,
        json={
            "fileName": "ref.png",
            "mimeType": "image/png",
            "fileSize": 20,
            "purpose": "reference_image",
            "rightsConfirmed": False,
        },
    )
    assert no_rights.status_code == 422
    too_big = client.post(
        "/v1/uploads/presign",
        headers=auth,
        json={
            "fileName": "ref.png",
            "mimeType": "image/png",
            "fileSize": 10**9,
            "purpose": "reference_image",
            "rightsConfirmed": True,
        },
    )
    assert too_big.json()["error"]["code"] == "UPLOAD_REJECTED"
    ok = client.post(
        "/v1/uploads/presign",
        headers=auth,
        json={
            "fileName": "ref.png",
            "mimeType": "image/png",
            "fileSize": 20,
            "purpose": "reference_image",
            "rightsConfirmed": True,
        },
    ).json()
    path = ok["uploadUrl"].replace("http://localhost:8000", "")
    spoofed = client.put(path, content=b"MZ-not-a-png-at-all")
    assert spoofed.status_code == 422
    good = client.put(path, content=b"\x89PNG\r\n\x1a\n" + b"0" * 12)
    assert good.status_code == 204
    assert client.put(path, content=b"\x89PNG\r\n\x1a\n").status_code == 422  # slot used


def test_export_and_delete_account(client, auth, container):
    c = create_character(client, auth, template_recipe(container, "tmpl_voltwood_guardian"))
    client.post("/v1/previews", json={"recipe": c["recipe"]}, headers=auth)
    export = client.get("/v1/me/export", headers=auth).json()
    assert export["characters"][0]["name"] == "Voltwood Guardian"
    usage = client.get("/v1/me/usage", headers=auth).json()
    assert usage["characters"] == 1
    me = client.get("/v1/me", headers=auth).json()
    assert client.delete("/v1/me", headers=auth).status_code == 204
    assert client.get("/v1/me", headers=auth).status_code == 401
    with container.db.session() as s:
        assert s.query(Character).count() == 0
        u = s.query(User).filter(User.display_name == "Deleted user").one()
        assert str(u.id) == me["id"] and u.email is None and u.deleted_at is not None
        assert s.query(AuditEvent).filter_by(action="account.deleted").count() == 1
        assert s.query(ModerationEvent).count() >= 1
    fresh = sign_in(client, "alice", "Alice")  # same subject can sign up again as a new account
    assert client.get("/v1/me", headers=fresh).json()["id"] != me["id"]
