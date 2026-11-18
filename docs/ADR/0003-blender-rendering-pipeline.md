# ADR 0003 — Rendering pipeline (procedural CPU renderer now, Blender worker next)

- **Status:** Accepted (procedural) · Blender path = spike, not yet validated · **Date:** 2026-11-17

## Context
Plan §8 calls for Blender in worker containers + FFmpeg muxing, with durable, idempotent jobs. Blender is not
available in this development environment, and no authored GLB assets exist yet.

## Decision
- A `Renderer` interface takes a validated, **data-only** `RenderPlan` (storyboard + resolved parts + catalogue data).
- **Default renderer: `ProceduralRenderer`** — Pillow frames (environment backdrop, characters in camera-preset
  framing, motion profiles per animation clip, power effects, subtitles, fades) + numpy audio stems (music cue, SFX,
  fictional "tone babble" voices) → **FFmpeg H.264/AAC MP4** with faststart. 480p draft / 720p final, 16:9 and 9:16,
  24 fps default, 15/30/60 s presets. Verified by `tests/test_real_render.py` (ffprobe shows h264 + aac, 15 s, 854x480).
- **Blender renderer (spike):** `app/workers/blender_scene.py` converts the plan to a JSON scene document consumed by a
  fixed, reviewed script `infrastructure/docker/blender/render_scene.py` (EEVEE). No user/LLM text is ever executed.
  `infrastructure/docker/blender-worker.Dockerfile` pins Blender 4.2 LTS. **Not yet validated** — Sprint 0 task
  remaining: build the image in CI, render the demo storyboard, compare timings vs the procedural renderer.
- Framing rule (plan §14.4): `character_unit()` clamps scale so characters plus their maximum motion lift never
  enter the subtitle band or leave the frame — tested across all camera presets, aspect ratios and scales.

## Reliability (plan §8.3)
Durable job rows; `Idempotency-Key` per user; at-least-once delivery made safe by an atomic **claim with lease**;
bounded exponential backoff on transient failures (`render_max_attempts`); permanent failures (malformed scene) are
not retried; cooperative cancellation between scenes; stranded-lease recovery on worker start; temp dir cleanup;
compute time recorded per job. GPU workers are not provisioned until benchmarks justify them.
