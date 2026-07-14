"""Render readable Vietnamese title and an optional logo over generated art."""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


@dataclass
class LayoutResult:
    image_bytes: bytes
    title_position: str
    font_size: int
    title_lines: int
    logo_rendered: bool

    def metadata(self) -> dict:
        return {
            "title_position": self.title_position,
            "font_size": self.font_size,
            "title_lines": self.title_lines,
            "logo_rendered": self.logo_rendered,
        }


def _font_path() -> str | None:
    candidates = [
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _font(size: int):
    path = _font_path()
    return ImageFont.truetype(path, size) if path else ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _fit_title(
    draw: ImageDraw.ImageDraw,
    title: str,
    max_width: int,
    max_height: int,
    image_width: int,
) -> tuple[object, list[str], int, int]:
    max_size = max(30, min(86, image_width // 12))
    min_size = max(16, image_width // 48)
    for size in range(max_size, min_size - 1, -2):
        font = _font(size)
        lines = _wrap(draw, title, font, max_width)
        spacing = max(5, size // 5)
        box = draw.multiline_textbbox((0, 0), "\n".join(lines), font=font, spacing=spacing)
        if len(lines) <= 6 and box[3] - box[1] <= max_height:
            return font, lines, size, spacing
    font = _font(min_size)
    lines = _wrap(draw, title, font, max_width)
    return font, lines, min_size, max(4, min_size // 5)


def _apply_scrim(image: Image.Image, position: str) -> Image.Image:
    width, height = image.size
    shade = Image.new("RGBA", image.size, (5, 8, 13, 220))
    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)

    if position == "bottom":
        start = int(height * 0.54)
        span = max(1, height - start)
        for y in range(start, height):
            alpha = int(210 * ((y - start) / span) ** 0.7)
            draw.line((0, y, width, y), fill=alpha)
    else:
        span = int(width * 0.62)
        for x in range(span):
            strength = 1 - (x / max(1, span - 1))
            alpha = int(205 * strength**1.7)
            px = width - 1 - x if position == "right" else x
            draw.line((px, 0, px, height), fill=alpha)
    return Image.composite(shade, image, mask)


def render_layout(
    image_bytes: bytes,
    *,
    title: str,
    title_position: str = "left",
    logo_path: Path | None = None,
) -> LayoutResult:
    with Image.open(io.BytesIO(image_bytes)) as source:
        image = source.convert("RGBA")

    width, height = image.size
    actual_position = "bottom" if len(title) > 110 else title_position
    image = _apply_scrim(image, actual_position)
    draw = ImageDraw.Draw(image)

    if actual_position == "bottom":
        max_width = int(width * 0.86)
        max_height = int(height * 0.32)
        x = int(width * 0.07)
        anchor_y = int(height * 0.63)
        align = "left"
    else:
        max_width = int(width * 0.42)
        max_height = int(height * 0.62)
        x = int(width * (0.54 if actual_position == "right" else 0.06))
        anchor_y = int(height * 0.19)
        align = "left"

    font, lines, font_size, spacing = _fit_title(draw, title, max_width, max_height, width)
    text = "\n".join(lines)
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing, align=align)
    text_height = bbox[3] - bbox[1]
    if actual_position != "bottom":
        y = max(anchor_y, (height - text_height) // 2)
    else:
        y = min(anchor_y, height - text_height - int(height * 0.08))

    shadow = max(2, width // 400)
    draw.multiline_text(
        (x + shadow, y + shadow),
        text,
        font=font,
        fill=(0, 0, 0, 185),
        spacing=spacing,
        align=align,
    )
    draw.multiline_text(
        (x, y),
        text,
        font=font,
        fill=(255, 255, 255, 255),
        spacing=spacing,
        align=align,
    )

    logo_rendered = False
    if logo_path and logo_path.exists():
        try:
            with Image.open(logo_path) as logo_source:
                logo = logo_source.convert("RGBA")
            logo.thumbnail((int(width * 0.16), int(height * 0.11)), Image.Resampling.LANCZOS)
            margin = int(min(width, height) * 0.045)
            logo_x = width - logo.width - margin if actual_position != "right" else margin
            logo_y = margin
            image.alpha_composite(logo, (logo_x, logo_y))
            logo_rendered = True
        except (OSError, ValueError):
            logo_rendered = False

    output = io.BytesIO()
    image.convert("RGB").save(output, "PNG", optimize=True)
    return LayoutResult(
        image_bytes=output.getvalue(),
        title_position=actual_position,
        font_size=font_size,
        title_lines=len(lines),
        logo_rendered=logo_rendered,
    )
