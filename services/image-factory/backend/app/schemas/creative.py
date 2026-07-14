"""Schemas for the structured creative-image workflow."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


StylePresetId = Literal[
    "editorial-tech",
    "human-story",
    "product-hero",
    "bold-thumbnail",
    "corporate-clean",
    "illustration-modern",
]
PurposeId = Literal["blog-cover", "thumbnail", "social-post"]
AspectRatioId = Literal["16:9", "1:1", "4:5", "9:16"]
QualityProfileId = Literal["draft", "standard", "publish"]
TitlePositionId = Literal["left", "right", "bottom"]


class CreativeBriefInput(BaseModel):
    title_text: str = Field(min_length=1, max_length=300)
    topic: str = Field(default="", max_length=300)
    content_summary: str = Field(default="", max_length=12000)
    audience: str = Field(default="", max_length=300)
    purpose: PurposeId = "blog-cover"
    aspect_ratio: AspectRatioId = "16:9"
    style_preset: StylePresetId = "editorial-tech"
    title_position: TitlePositionId = "left"
    quality_profile: QualityProfileId = "standard"
    must_include: list[str] = Field(default_factory=list, max_length=8)
    must_avoid: list[str] = Field(default_factory=list, max_length=12)
    visual_prompt_override: str = Field(default="", max_length=4000)
    logo_asset_id: str | None = Field(default=None, max_length=100)
    apply_layout: bool = True

    @field_validator("title_text", "topic", "content_summary", "audience", "visual_prompt_override")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("must_include", "must_avoid")
    @classmethod
    def clean_lists(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            item = str(value).strip()
            if item and item not in cleaned:
                cleaned.append(item[:160])
        return cleaned


class VisualBrief(BaseModel):
    concept: str
    primary_subject: str
    supporting_objects: list[str] = Field(default_factory=list)
    environment: str
    action: str
    composition: str
    camera: str
    lighting: str
    palette: list[str]
    mood: str
    render_style: str
    text_safe_area: str
    must_include: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0, le=1)


class CreativePackageOut(BaseModel):
    brief: VisualBrief
    compiled_prompt: str
    negative_prompt: str
    source: Literal["llm", "heuristic"]
    style_preset: str
    width: int
    height: int
    steps: int
    cfg: float


class StylePresetOut(BaseModel):
    id: str
    label: str
    description: str


class LogoAssetOut(BaseModel):
    id: str
    filename: str
