"""Procedural, team-authored audio: music cues, sound effects and the 'tone babble' fictional voices.

Everything here is generated from code we own, so it is licence-clean (lic_cv_original_v1). A real TTS
engine plugs in through SpeechGenerationProvider once its terms are reviewed. Tracks are kept separate
(dialogue / sfx / music stems) until the final mix (plan §7.4).
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Any

import numpy as np

from app.services.ai.providers import ProviderInfo, stable_int

SAMPLE_RATE = 44100
SCALES = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10], "pentatonic": [0, 2, 4, 7, 9]}


def _env(n: int, attack: float = 0.01, release: float = 0.08) -> np.ndarray:
    env = np.ones(n)
    a, r = max(1, int(attack * SAMPLE_RATE)), max(1, int(release * SAMPLE_RATE))
    env[: min(a, n)] = np.linspace(0, 1, min(a, n))
    env[-min(r, n) :] *= np.linspace(1, 0, min(r, n))
    return env


class ToneBabbleSpeechProvider:
    """Fictional, non-impersonating 'voice': syllable-rate pitched babble shaped by the text."""

    info = ProviderInfo(
        name="cv_tone_babble_v1",
        version="1.0",
        kind="speech",
        terms_url=None,
        cost_per_call_usd=0.0,
        typical_latency_ms=2,
        local=True,
    )

    def synthesize(self, text: str, voice: dict[str, Any], sample_rate: int = SAMPLE_RATE) -> np.ndarray:
        base = float(voice.get("baseHz", 200))
        robotic = "robotic" in voice.get("id", "")
        syllables = max(1, len(text) // 3)
        seg = int(0.075 * sample_rate)
        out = []
        for i in range(syllables):
            ch = text[(i * 3) % len(text)] if text else "a"
            pitch = base * (1 + ((ord(ch) % 7) - 3) * 0.05)
            if text.endswith("?") and i > syllables - 3:
                pitch *= 1.2
            t = np.arange(seg) / sample_rate
            wave_ = (
                np.sign(np.sin(2 * np.pi * pitch * t)) * 0.5
                if robotic
                else (np.sin(2 * np.pi * pitch * t) + 0.3 * np.sin(4 * np.pi * pitch * t))
            )
            out.append(wave_ * _env(seg, 0.01, 0.03) * 0.28)
            if ch in " ,.!?":
                out.append(np.zeros(seg // 2))
        return np.concatenate(out)


def synth_sfx(kind: str, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    rng = np.random.default_rng(stable_int(kind))
    n = int(0.45 * sample_rate)
    t = np.arange(n) / sample_rate
    if kind == "noise_sweep":
        sig = rng.normal(0, 1, n) * np.sin(np.pi * t / t[-1]) * 0.25
    elif kind == "square_drop":
        f = np.linspace(1200, 200, n)
        sig = np.sign(np.sin(2 * np.pi * np.cumsum(f) / sample_rate)) * 0.18
    elif kind == "bell":
        sig = (np.sin(2 * np.pi * 880 * t) + 0.5 * np.sin(2 * np.pi * 1320 * t)) * np.exp(-6 * t) * 0.3
    elif kind == "low_hit":
        sig = np.sin(2 * np.pi * 70 * t) * np.exp(-12 * t) * 0.6
    else:  # blip
        sig = np.sin(2 * np.pi * np.linspace(500, 900, n) * t) * np.exp(-14 * t) * 0.35
    return sig * _env(n)


def synth_music(cue: dict[str, Any], seconds: float, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    bpm = cue.get("bpm", 100)
    scale = SCALES.get(cue.get("scale", "major"), SCALES["major"])
    beat = 60.0 / bpm
    n_total = int(seconds * sample_rate)
    out = np.zeros(n_total)
    root = 220.0
    progression = [0, 5, 3, 4]
    rng = np.random.default_rng(stable_int(cue.get("id", "music")))
    step = 0
    pos = 0
    note_len = int(beat * sample_rate / 2)
    while pos < n_total:
        chord_root = progression[(step // 8) % len(progression)]
        degree = (chord_root + int(rng.integers(0, 5))) % len(scale)
        freq = root * 2 ** (scale[degree] / 12) * (2 if step % 4 == 0 else 1)
        n = min(note_len, n_total - pos)
        t = np.arange(n) / sample_rate
        tone = (np.sin(2 * np.pi * freq * t) * 0.12 + np.sin(2 * np.pi * freq / 2 * t) * 0.06) * _env(n, 0.005, 0.1)
        out[pos : pos + n] += tone
        if step % 2 == 0:  # soft kick
            k = min(int(0.12 * sample_rate), n_total - pos)
            tk = np.arange(k) / sample_rate
            out[pos : pos + k] += np.sin(2 * np.pi * 60 * tk) * np.exp(-25 * tk) * 0.25
        pos += note_len
        step += 1
    return out


def mix_tracks(length: int, stems: list[tuple[np.ndarray, int, float]]) -> np.ndarray:
    out = np.zeros(length)
    for sig, start, gain in stems:
        if start >= length:
            continue
        n = min(len(sig), length - start)
        out[start : start + n] += sig[:n] * gain
    peak = np.max(np.abs(out)) or 1.0
    return out / max(peak, 1.0) * 0.9


def write_wav(path: Path, samples: np.ndarray, sample_rate: int = SAMPLE_RATE) -> None:
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())
