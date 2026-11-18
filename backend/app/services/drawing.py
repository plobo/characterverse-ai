"""2D projection renderer for procedural parts (thumbnails and procedural video frames)."""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageDraw


def hex_rgb(color: str) -> tuple[int, int, int]:
    c = color.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def shade(rgb: tuple[int, int, int], f: float) -> tuple[int, int, int]:
    if f >= 1:
        return tuple(min(255, int(v + (255 - v) * (f - 1))) for v in rgb)  # type: ignore[return-value]
    return tuple(max(0, int(v * f)) for v in rgb)  # type: ignore[return-value]


def tint(rgb: tuple[int, int, int], t: tuple[int, int, int]) -> tuple[int, int, int]:
    return tuple(int(a * b / 255) for a, b in zip(rgb, t, strict=True))  # type: ignore[return-value]


def draw_character(
    draw: ImageDraw.ImageDraw,
    parts: list[dict[str, Any]],
    origin: tuple[float, float],
    scale: float,
    light: tuple[int, int, int] = (255, 255, 255),
    offset: tuple[float, float] = (0.0, 0.0),
    lean: float = 0.0,
    flip: bool = False,
) -> None:
    """Front orthographic projection; painter's sort on z. origin is the screen point of the feet."""
    ox, oy = origin
    for part in sorted(parts, key=lambda p: p["position"][2] - p["size"][2] / 2):
        x, y, _ = part["position"]
        sx, sy, _ = part["size"]
        if flip:
            x = -x
        x += lean * y + offset[0]
        y += offset[1]
        cx, cy = ox + x * scale, oy - y * scale
        hw, hh = max(sx * scale / 2, 1), max(sy * scale / 2, 1)
        base = tint(hex_rgb(part["color"]), light)
        outline = shade(base, 0.55)
        box = [cx - hw, cy - hh, cx + hw, cy + hh]
        shape = part["shape"]
        if shape == "sphere":
            draw.ellipse(box, fill=base, outline=outline, width=max(1, int(scale * 0.012)))
            draw.ellipse([cx - hw * 0.55, cy - hh * 0.75, cx - hw * 0.05, cy - hh * 0.25], fill=shade(base, 1.25))
        elif shape == "capsule":
            draw.rounded_rectangle(
                box, radius=min(hw, hh), fill=base, outline=outline, width=max(1, int(scale * 0.012))
            )
            draw.rounded_rectangle(
                [cx - hw * 0.6, cy - hh * 0.85, cx - hw * 0.1, cy + hh * 0.3], radius=hw * 0.25, fill=shade(base, 1.18)
            )
        elif shape == "box":
            draw.rounded_rectangle(
                box, radius=min(hw, hh) * 0.18, fill=base, outline=outline, width=max(1, int(scale * 0.012))
            )
            draw.rectangle([cx - hw * 0.8, cy - hh * 0.85, cx + hw * 0.8, cy - hh * 0.55], fill=shade(base, 1.15))
        elif shape == "cylinder":
            draw.rectangle(box, fill=base, outline=outline)
            draw.ellipse([cx - hw, cy - hh - hw * 0.25, cx + hw, cy - hh + hw * 0.25], fill=shade(base, 1.2))
        elif shape == "cone":
            draw.polygon([(cx - hw, cy + hh), (cx + hw, cy + hh), (cx, cy - hh)], fill=base, outline=outline)


def vertical_gradient(size: tuple[int, int], top: str, bottom: str) -> Image.Image:
    w, h = size
    t, b = hex_rgb(top), hex_rgb(bottom)
    grad = Image.new("RGB", (1, h))
    for yy in range(h):
        f = yy / max(h - 1, 1)
        grad.putpixel((0, yy), tuple(int(t[i] + (b[i] - t[i]) * f) for i in range(3)))
    return grad.resize((w, h))


def render_thumbnail(parts: list[dict[str, Any]], size: int = 512, background: str = "#EDE9FF") -> bytes:
    import io

    img = vertical_gradient((size, size), background, "#FFFFFF")
    draw = ImageDraw.Draw(img)
    top = max(p["position"][1] + p["size"][1] / 2 for p in parts)
    width = max(abs(p["position"][0]) + p["size"][0] / 2 for p in parts) * 2
    scale = min(size * 0.8 / max(top, 0.1), size * 0.8 / max(width, 0.1))
    draw.ellipse([size * 0.3, size * 0.86, size * 0.7, size * 0.93], fill=(205, 200, 230))
    draw_character(draw, parts, (size / 2, size * 0.9), scale)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
