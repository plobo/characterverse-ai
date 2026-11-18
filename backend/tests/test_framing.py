"""Plan §14.4: camera framing must not cut off important character parts; subtitles must fit the frame."""

from __future__ import annotations

import pytest
from PIL import ImageFont

from app.services.assembly import assemble_parts
from app.workers.renderer import MAX_MOTION_LIFT, character_unit, wrap_subtitle

CAMERA_ZOOMS = [0.8, 1.0, 1.15, 1.45]


@pytest.mark.parametrize("template", ["tmpl_voltwood_guardian", "tmpl_nova_sprocket", "tmpl_zibba", "tmpl_mossy_pip"])
@pytest.mark.parametrize("zoom", CAMERA_ZOOMS)
@pytest.mark.parametrize("scale", [1.0, 1.5])
@pytest.mark.parametrize("size", [(854, 480), (480, 854)])
def test_character_never_cropped_at_top(container, template, zoom, scale, size):
    width, height = size
    parts = assemble_parts(container.catalog.get(template).data["recipe"], container.catalog)
    unit = character_unit(parts, width, height, zoom, scale)
    feet_y = height * 0.86
    top = max(p["position"][1] + p["size"][1] / 2 for p in parts)
    highest_pixel = feet_y - (top + MAX_MOTION_LIFT) * unit
    assert highest_pixel >= height * 0.15, "head would collide with subtitles or leave the frame"
    half_width = max(abs(p["position"][0]) + p["size"][0] / 2 for p in parts) * unit
    assert half_width * 2 <= width * 0.45


def test_long_subtitles_wrap_inside_frame():
    font = ImageFont.load_default(size=18)
    line = "Voltwood Guardian: Hi, I'm Voltwood Guardian! Today we find the glowing map in the crystal forest."
    lines = wrap_subtitle(line, font, max_width=400)
    assert len(lines) >= 2
    assert all(font.getlength(x) <= 400 for x in lines)
    assert " ".join(lines) == line
