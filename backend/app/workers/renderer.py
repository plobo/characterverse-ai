"""Procedural video renderer: storyboard -> frames (Pillow) + audio stems (numpy) -> FFmpeg H.264/AAC MP4.

This is the CPU-only MVP renderer. The Blender worker (app/workers/blender_scene.py, ADR 0003) consumes the
same RenderPlan, so the two are interchangeable behind `Renderer`.
"""

from __future__ import annotations

import math
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.services.drawing import draw_character, hex_rgb, vertical_gradient
from app.workers.audio import (
    SAMPLE_RATE,
    ToneBabbleSpeechProvider,
    mix_tracks,
    synth_music,
    synth_sfx,
    write_wav,
)

SLOT_X = {"far_left": 0.12, "left": 0.3, "center": 0.5, "right": 0.7, "far_right": 0.88}
RESOLUTIONS = {
    ("draft", "16:9"): (854, 480),
    ("draft", "9:16"): (480, 854),
    ("final", "16:9"): (1280, 720),
    ("final", "9:16"): (720, 1280),
}


MAX_MOTION_LIFT = 0.75  # highest dy any motion profile produces (soar: 0.6 + 0.1), in character units
FEET_Y = 0.86
TOP_SAFE = 0.15  # top band reserved for subtitles


def character_unit(parts: list[dict[str, Any]], width: int, height: int, zoom: float, scale: float) -> float:
    """Pixels per character unit for a camera preset, clamped so the head (plus any jump/flight lift) stays below
    the subtitle band and the character never fills more than ~45% of the frame width (plan §14.4)."""
    top = max(p["position"][1] + p["size"][1] / 2 for p in parts)
    half_width = max(abs(p["position"][0]) + p["size"][0] / 2 for p in parts)
    wanted = height * 0.36 * zoom * scale
    fit_height = height * (FEET_Y - TOP_SAFE) / (top + MAX_MOTION_LIFT)
    fit_width = width * 0.45 / (2 * half_width)
    return min(wanted, fit_height, fit_width)


def wrap_subtitle(text: str, font: Any, max_width: float) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        candidate = f"{current} {word}".strip()
        if current and font.getlength(candidate) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


class TransientRenderError(Exception):
    code = "RENDER_TRANSIENT"


class PermanentRenderError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class RenderCancelled(Exception):
    pass


@dataclass
class RenderPlan:
    width: int
    height: int
    fps: int
    storyboard: dict[str, Any]
    character_parts: dict[str, list[dict[str, Any]]]
    character_names: dict[str, str]
    character_voices: dict[str, dict[str, Any]]
    character_powers: dict[str, list[str]]
    catalog_data: dict[str, dict[str, Any]]  # asset id -> manifest data


def motion_offsets(motion: str, t: float, dur: float) -> tuple[float, float, float, bool]:
    """Returns (dx, dy, lean, flip) in character units for an animation clip's motion profile."""
    s = math.sin
    p = t / max(dur, 1e-3)
    if motion == "bob":
        return 0, 0.03 * s(2 * math.pi * t * 1.2), 0, False
    if motion == "stride":
        return (p - 0.5) * 0.8, 0.03 * abs(s(2 * math.pi * t * 2)), 0.03, False
    if motion == "dash":
        return (p - 0.5) * 1.6, 0.05 * abs(s(2 * math.pi * t * 3)), 0.12, False
    if motion == "hop":
        return 0, 0.35 * max(0.0, s(2 * math.pi * t * 1.1)), 0, False
    if motion == "sway":
        return 0, 0, 0.07 * s(2 * math.pi * t), False
    if motion == "lean":
        return 0, 0, 0.09, False
    if motion == "shake":
        return 0.03 * s(2 * math.pi * t * 8), 0.02 * abs(s(2 * math.pi * t * 4)), 0, False
    if motion == "nod":
        return 0, 0.02 * s(2 * math.pi * t * 3), 0.02 * s(2 * math.pi * t * 1.5), False
    if motion == "spin":
        return 0, 0.04 * abs(s(2 * math.pi * t * 2)), 0, s(2 * math.pi * t) < 0
    if motion == "float":
        return 0, 0.25 + 0.06 * s(2 * math.pi * t), 0, False
    if motion == "soar":
        return (p - 0.5) * 1.0, 0.6 + 0.1 * s(2 * math.pi * t), 0.15, False
    if motion == "lunge":
        return 0.25 * max(0.0, s(2 * math.pi * t * 1.5)), 0, 0.1, False
    if motion == "recoil":
        return -0.15 * math.exp(-3 * t), 0, -0.08 * math.exp(-3 * t), False
    if motion == "drop":
        return 0, 0, min(0.6, t * 0.8), False
    if motion == "rise":
        return 0, 0, max(0.0, 0.6 - t * 0.8), False
    return 0, 0, 0, False


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # pragma: no cover - very old Pillow
        return ImageFont.load_default()


class ProceduralRenderer:
    name = "procedural-pillow-ffmpeg"

    def __init__(self, ffmpeg_exe: str, timeout_seconds: int = 900):
        self.ffmpeg = ffmpeg_exe
        self.timeout = timeout_seconds

    # ------------------------------------------------------------------ audio
    def render_audio(self, plan: RenderPlan, path: Path) -> int:
        sb = plan.storyboard
        total_ms = sum(s["durationMs"] for s in sb["scenes"])
        length = int(total_ms / 1000 * SAMPLE_RATE)
        stems: list[tuple[np.ndarray, int, float]] = []
        if sb.get("musicCueId"):
            stems.append((synth_music(plan.catalog_data[sb["musicCueId"]], total_ms / 1000), 0, 0.55))
        speech = ToneBabbleSpeechProvider()
        offset = 0
        for scene in sb["scenes"]:
            for i, sfx_id in enumerate(scene["soundEffectIds"]):
                start = offset + 250 + i * 900
                stems.append((synth_sfx(plan.catalog_data[sfx_id]["synth"]), int(start / 1000 * SAMPLE_RATE), 0.8))
            for d in scene["dialogue"]:
                voice = plan.character_voices.get(d["characterId"], {"baseHz": 200})
                stems.append(
                    (speech.synthesize(d["line"], voice), int((offset + d["startMs"]) / 1000 * SAMPLE_RATE), 1.0)
                )
            offset += scene["durationMs"]
        write_wav(path, mix_tracks(length, stems))
        return total_ms

    # ------------------------------------------------------------------ frames
    def _background(self, plan: RenderPlan, scene: dict[str, Any]) -> Image.Image:
        env = plan.catalog_data[scene["environmentId"]]
        w, h = plan.width, plan.height
        img = vertical_gradient((w, h), env["skyTop"], env["skyBottom"])
        draw = ImageDraw.Draw(img)
        horizon = int(h * 0.72)
        draw.rectangle([0, horizon, w, h], fill=hex_rgb(env["ground"]))
        # simple original set dressing, deterministic per environment
        seed = sum(ord(c) for c in scene["environmentId"])
        for i in range(7):
            x = (seed * (i + 3) * 37) % w
            bw = w * (0.05 + ((seed + i) % 5) * 0.015)
            bh = h * (0.12 + ((seed * (i + 1)) % 7) * 0.03)
            col = tuple(max(0, c - 30) for c in hex_rgb(env["skyBottom"]))
            if scene["environmentId"] in ("env_crystal_forest_01",):
                draw.polygon([(x - bw / 2, horizon), (x + bw / 2, horizon), (x, horizon - bh)], fill=col)
            else:
                draw.rounded_rectangle([x - bw / 2, horizon - bh, x + bw / 2, horizon], radius=bw * 0.15, fill=col)
        if scene["environmentId"] in ("env_moon_base_01", "env_neon_alley_01"):
            for i in range(40):
                sx, sy = (seed * (i + 7) * 53) % w, (seed * (i + 11) * 29) % int(h * 0.6)
                draw.ellipse([sx, sy, sx + 2, sy + 2], fill=(255, 255, 240))
        return img

    def _frames(self, plan: RenderPlan, cancel_check: Callable[[], bool], on_scene: Callable[[int, int], None]):
        font = _font(max(14, plan.height // 26))
        small = _font(max(12, plan.height // 34))
        n_scenes = len(plan.storyboard["scenes"])
        for si, scene in enumerate(plan.storyboard["scenes"]):
            if cancel_check():
                raise RenderCancelled()
            on_scene(si, n_scenes)
            bg = self._background(plan, scene)
            shadow = tuple(int(c * 0.6) for c in hex_rgb(plan.catalog_data[scene["environmentId"]]["ground"]))
            light = hex_rgb(plan.catalog_data[scene["lightingPresetId"]]["tint"])
            zoom = plan.catalog_data[scene["cameraPresetId"]]["zoom"]
            dur = scene["durationMs"] / 1000
            frames = max(1, int(round(dur * plan.fps)))
            for fi in range(frames):
                t = fi / plan.fps
                img = bg.copy()
                draw = ImageDraw.Draw(img)
                for sc in scene["characters"]:
                    parts = plan.character_parts.get(sc["characterId"])
                    if not parts:
                        continue
                    clip = plan.catalog_data.get(sc["actionId"], {"motion": "still"})
                    dx, dy, lean, flip = motion_offsets(clip["motion"], t, dur)
                    unit = character_unit(parts, plan.width, plan.height, zoom, sc["scale"])
                    feet = (plan.width * SLOT_X[sc["position"]], plan.height * FEET_Y)
                    draw.ellipse(
                        [feet[0] - unit * 0.4, feet[1] - unit * 0.06, feet[0] + unit * 0.4, feet[1] + unit * 0.06],
                        fill=shadow,
                    )
                    if sc["actionId"] in ("action_combo_01", "fly", "hover", "victory"):
                        for power in plan.character_powers.get(sc["characterId"], [])[:2]:
                            color = hex_rgb(plan.catalog_data[power]["effectColor"])
                            for k in range(6):
                                ang = t * 3 + k * math.pi / 3
                                px = feet[0] + (dx * unit) + math.cos(ang) * unit * 0.6
                                py = feet[1] - unit * (1.0 + dy) + math.sin(ang) * unit * 0.6
                                r = unit * 0.04
                                draw.ellipse([px - r, py - r, px + r, py + r], fill=color)
                    draw_character(draw, parts, feet, unit, light, (dx, dy), lean, flip)
                for d in scene["dialogue"]:
                    start = d["startMs"] / 1000
                    end = start + 1.2 + len(d["line"]) * 0.055
                    if start <= t <= end:
                        label = f"{plan.character_names.get(d['characterId'], '')}: {d['line']}"
                        lines = wrap_subtitle(label, font, plan.width * 0.92 - 32)
                        if len(lines) > 2:
                            lines = [lines[0], " ".join(lines[1:])]
                            while font.getlength(lines[1] + "…") > plan.width * 0.92 - 32:
                                lines[1] = lines[1][:-1]
                            lines[1] += "…"
                        tw = max(draw.textlength(x, font=font) for x in lines)
                        bw = tw + 32
                        x0 = (plan.width - bw) / 2
                        y0 = plan.height * 0.02
                        line_h = font.size * 1.25
                        bh = line_h * len(lines) + font.size * 0.6
                        draw.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=12, fill=(20, 16, 40))
                        for li, text in enumerate(lines):
                            draw.text(
                                (x0 + 16, y0 + font.size * 0.3 + li * line_h), text, font=font, fill=(255, 255, 255)
                            )
                draw.text(
                    (12, plan.height - small.size * 1.6),
                    f"{si + 1}/{n_scenes}  {scene.get('title', '')}",
                    font=small,
                    fill=(255, 255, 255),
                )
                if scene["transition"] == "fade" and t < 0.35:
                    img = Image.blend(Image.new("RGB", img.size, (0, 0, 0)), img, t / 0.35)
                yield img

    # ------------------------------------------------------------------ pipeline
    def render(
        self, plan: RenderPlan, work: Path, cancel_check: Callable[[], bool], progress: Callable[[str, int], None]
    ) -> tuple[Path, Path, int]:
        work.mkdir(parents=True, exist_ok=True)
        audio = work / "mix.wav"
        out = work / "output.mp4"
        thumb = work / "thumbnail.png"
        progress("rendering_scenes", 10)
        duration_ms = self.render_audio(plan, audio)
        cmd = [
            self.ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{plan.width}x{plan.height}",
            "-r",
            str(plan.fps),
            "-i",
            "-",
            "-i",
            str(audio),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(out),
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        first = None
        try:

            def on_scene(i: int, n: int) -> None:
                progress("rendering_scenes", 10 + int(70 * i / n))

            for frame in self._frames(plan, cancel_check, on_scene):
                if first is None:
                    first = frame
                proc.stdin.write(frame.tobytes())  # type: ignore[union-attr]
            proc.stdin.close()  # type: ignore[union-attr]
            progress("composing", 85)
            proc.wait(timeout=self.timeout)
        except BrokenPipeError as exc:
            raise TransientRenderError(f"ffmpeg exited early: {proc.stderr.read().decode()[-500:]}") from exc
        except BaseException:
            proc.kill()
            raise
        if proc.returncode != 0:
            raise TransientRenderError(f"ffmpeg failed: {proc.stderr.read().decode()[-500:]}")
        if first is not None:
            first.save(thumb)
        return out, thumb, duration_ms
