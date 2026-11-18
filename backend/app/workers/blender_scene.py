"""Blender worker adapter (ADR 0003). Converts a validated RenderPlan into a *data-only* scene description
that a fixed, reviewed Blender script (infrastructure/docker/blender/render_scene.py) consumes.

Nothing user-supplied is ever executed: the LLM and clients produce IDs + numbers; this module emits JSON.
Status: spike - exercised by unit tests for the scene document; the Blender execution path itself must be
validated in the worker container (see docs/ADR/0003-blender-rendering-pipeline.md).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.workers.renderer import SLOT_X, RenderPlan, TransientRenderError

SCRIPT = Path(__file__).resolve().parents[3] / "infrastructure" / "docker" / "blender" / "render_scene.py"


def scene_document(plan: RenderPlan) -> dict[str, Any]:
    scenes = []
    for scene in plan.storyboard["scenes"]:
        env = plan.catalog_data[scene["environmentId"]]
        scenes.append(
            {
                "durationFrames": max(1, round(scene["durationMs"] / 1000 * plan.fps)),
                "environment": {
                    "id": scene["environmentId"],
                    "skyTop": env["skyTop"],
                    "skyBottom": env["skyBottom"],
                    "ground": env["ground"],
                },
                "camera": {
                    "preset": scene["cameraPresetId"],
                    "zoom": plan.catalog_data[scene["cameraPresetId"]]["zoom"],
                },
                "light": plan.catalog_data[scene["lightingPresetId"]]["tint"],
                "actors": [
                    {
                        "characterId": sc["characterId"],
                        "x": (SLOT_X[sc["position"]] - 0.5) * 6.0,
                        "scale": sc["scale"],
                        "motion": plan.catalog_data[sc["actionId"]]["motion"],
                        "parts": plan.character_parts[sc["characterId"]],
                    }
                    for sc in scene["characters"]
                ],
            }
        )
    return {"version": 1, "width": plan.width, "height": plan.height, "fps": plan.fps, "scenes": scenes}


class BlenderRenderer:
    name = "blender-eevee"

    def __init__(self, blender_exe: str = "blender", timeout_seconds: int = 1800):
        self.blender = shutil.which(blender_exe) or blender_exe
        self.timeout = timeout_seconds

    def render_frames(self, plan: RenderPlan, work: Path) -> Path:
        work.mkdir(parents=True, exist_ok=True)
        doc = work / "scene.json"
        doc.write_text(json.dumps(scene_document(plan)))
        frames = work / "frames"
        cmd = [self.blender, "--background", "--factory-startup", "--python", str(SCRIPT), "--", str(doc), str(frames)]
        try:
            subprocess.run(cmd, check=True, timeout=self.timeout, capture_output=True)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
            raise TransientRenderError(f"blender failed: {exc}") from exc
        return frames
