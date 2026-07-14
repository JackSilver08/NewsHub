"""Fast, local quality checks that reject blank or nearly-flat generations."""

from __future__ import annotations

import io
from dataclasses import asdict, dataclass

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError


@dataclass
class QualityAssessment:
    accepted: bool
    reason: str | None
    entropy: float
    luminance_stddev: float
    edge_mean: float

    def to_dict(self) -> dict:
        return asdict(self)


def assess_image(data: bytes) -> QualityAssessment:
    try:
        with Image.open(io.BytesIO(data)) as source:
            image = source.convert("RGB")
            image.thumbnail((384, 384))
    except (UnidentifiedImageError, OSError, ValueError):
        return QualityAssessment(False, "invalid_image", 0.0, 0.0, 0.0)

    gray = image.convert("L")
    entropy = float(gray.entropy())
    stddev = float(ImageStat.Stat(gray).stddev[0])
    edges = gray.filter(ImageFilter.FIND_EDGES)
    if edges.width > 8 and edges.height > 8:
        edges = edges.crop((4, 4, edges.width - 4, edges.height - 4))
    edge_mean = float(ImageStat.Stat(edges).mean[0])

    if entropy < 1.2:
        return QualityAssessment(False, "near_single_color", entropy, stddev, edge_mean)
    if edge_mean < 1.2 and entropy < 7.2:
        return QualityAssessment(False, "flat_or_empty_scene", entropy, stddev, edge_mean)
    if stddev < 7.0 and edge_mean < 2.0:
        return QualityAssessment(False, "low_visual_information", entropy, stddev, edge_mean)
    return QualityAssessment(True, None, entropy, stddev, edge_mean)

