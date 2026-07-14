"""Compile a model-facing prompt from a validated visual brief."""

from __future__ import annotations

from app.schemas.creative import VisualBrief
from app.services.style_presets import get_style


BASE_NEGATIVE = [
    "text",
    "letters",
    "words",
    "caption",
    "watermark",
    "logo",
    "empty scene",
    "plain gradient background",
    "no subject",
    "bad anatomy",
    "malformed hands",
    "duplicated objects",
    "cropped face",
    "low contrast",
    "cluttered composition",
]


def compile_prompt(brief: VisualBrief, style_preset: str) -> str:
    style = get_style(style_preset)
    supporting = ", ".join(brief.supporting_objects)
    required = ", ".join(brief.must_include)
    palette = ", ".join(brief.palette)

    segments = [
        f"required visible subjects: {required}" if required else "",
        f"{brief.primary_subject}, {brief.action}",
        f"in {brief.environment}",
        f"supporting objects: {supporting}" if supporting else "",
        f"composition: {brief.composition}; reserve {brief.text_safe_area} as clean negative space",
        f"camera: {brief.camera}",
        f"lighting: {brief.lighting}",
        f"style: {brief.render_style}; {style['layout']}",
        f"color palette: {palette}",
        f"mood: {brief.mood}",
        f"keep every required element clearly visible and recognizable: {required}" if required else "",
        "one coherent real scene, tangible subject, strong focal point, professional art direction",
        "no typography or graphic text inside the generated image",
    ]
    return ". ".join(segment.strip(" .") for segment in segments if segment).strip() + "."


def compile_negative_prompt(brief: VisualBrief, user_negative: str = "") -> str:
    terms = [*BASE_NEGATIVE, *brief.must_avoid]
    if user_negative:
        terms.extend(part.strip() for part in user_negative.split(","))
    unique: list[str] = []
    for term in terms:
        clean = term.strip()
        if clean and clean.lower() not in {value.lower() for value in unique}:
            unique.append(clean)
    return ", ".join(unique)
