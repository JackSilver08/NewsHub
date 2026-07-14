"""Mock generation backend.

Produces an unmistakable deterministic placeholder from the prompt+seed so the entire
pipeline (queue, storage, thumbnails, gallery, progress, resume) can be tested
without a GPU or a running ComfyUI. Enable with COMFYUI_ENABLED=false.
"""

from __future__ import annotations

import hashlib
import io
import time

from PIL import Image, ImageDraw, ImageFont

from app.comfyui.generator import GenerationRequest, GenerationResult
from app.core.logging import get_logger

logger = get_logger(__name__)


def _color_from(seed_material: str, offset: int = 0) -> tuple[int, int, int]:
    digest = hashlib.sha256(f"{seed_material}:{offset}".encode()).digest()
    return digest[0], digest[1], digest[2]


def _gradient(width: int, height: int, c1, c2) -> Image.Image:
    base = Image.new("RGB", (width, height), c1)
    top = Image.new("RGB", (width, height), c2)
    mask = Image.new("L", (width, height))
    mask_data = [int(255 * (y / max(height - 1, 1))) for y in range(height) for _ in range(width)]
    mask.putdata(mask_data)
    return Image.composite(top, base, mask)


class MockGenerator:
    backend_name = "mock"

    def generate(self, req: GenerationRequest) -> GenerationResult:
        start = time.monotonic()
        # Simulate a little work so progress/ETA behave realistically.
        time.sleep(0.4)

        material = f"{req.prompt}|{req.seed}|{req.model}"
        c1 = _color_from(material, 0)
        c2 = _color_from(material, 1)
        img = _gradient(req.width, req.height, tuple(v // 4 for v in c1), tuple(v // 3 for v in c2))

        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arialbd.ttf", max(22, req.width // 16))
            small = ImageFont.truetype("arial.ttf", max(13, req.width // 46))
        except OSError:
            font = ImageFont.load_default()
            small = ImageFont.load_default()

        spacing = max(28, req.width // 12)
        for x in range(-req.height, req.width + req.height, spacing):
            draw.line((x, 0, x + req.height, req.height), fill=(255, 255, 255), width=1)

        label = "MOCK PREVIEW"
        sublabel = "NO AI MODEL IS GENERATING THIS IMAGE"
        label_box = draw.textbbox((0, 0), label, font=font)
        sub_box = draw.textbbox((0, 0), sublabel, font=small)
        center_y = req.height // 2
        padding = max(18, req.width // 36)
        box_width = max(label_box[2], sub_box[2]) + padding * 2
        box_height = label_box[3] + sub_box[3] + padding * 2
        left = (req.width - box_width) // 2
        top = center_y - box_height // 2
        draw.rounded_rectangle(
            (left, top, left + box_width, top + box_height),
            radius=max(8, req.width // 80),
            fill=(8, 10, 14),
            outline=(255, 191, 71),
            width=max(2, req.width // 256),
        )
        draw.text(((req.width - label_box[2]) // 2, top + padding), label, fill=(255, 255, 255), font=font)
        draw.text(
            ((req.width - sub_box[2]) // 2, top + padding + label_box[3] + 8),
            sublabel,
            fill=(255, 191, 71),
            font=small,
        )
        footer = f"seed={req.seed} | {req.width}x{req.height}"
        draw.text((16, req.height - max(26, req.height // 18)), footer, fill=(210, 214, 224), font=small)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return GenerationResult(
            image_bytes=buf.getvalue(),
            width=req.width,
            height=req.height,
            seed=req.seed,
            backend=self.backend_name,
            duration_seconds=time.monotonic() - start,
        )

    def health_check(self) -> bool:
        return True
