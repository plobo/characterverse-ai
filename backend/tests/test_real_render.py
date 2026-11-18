"""End-to-end: real procedural frames + synthesized audio + FFmpeg -> playable H.264/AAC MP4."""

from __future__ import annotations

import subprocess

import imageio_ffmpeg

from tests.test_renders import project_with_storyboard, submit


def test_real_mp4_with_audio(client, auth, container, tmp_path):
    container.extras.pop("renderer_factory")
    p = project_with_storyboard(client, auth, container, seconds=15)
    job = submit(client, auth, p["id"]).json()
    job = client.get(f"/v1/renders/{job['id']}", headers=auth).json()
    assert job["status"] == "completed", job
    dl = client.get(f"/v1/renders/{job['id']}/download-url", headers=auth).json()
    video = client.get(dl["url"].replace("http://localhost:8000", ""))
    assert video.headers["content-type"] == "video/mp4"
    path = tmp_path / "out.mp4"
    path.write_bytes(video.content)
    probe = subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True, text=True
    ).stderr
    assert "Video: h264" in probe and "Audio: aac" in probe
    assert "Duration: 00:00:15" in probe or "Duration: 00:00:14.9" in probe, probe
    assert "854x480" in probe
    thumb = client.get(dl["thumbnailUrl"].replace("http://localhost:8000", ""))
    assert thumb.content[:8] == b"\x89PNG\r\n\x1a\n"
