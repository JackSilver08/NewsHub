"""Generation request/response abstraction shared by all backends."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GenerationRequest:
    prompt: str
    negative_prompt: str = ""
    seed: int = 0
    width: int = 1024
    height: int = 1024
    steps: int = 25
    cfg: float = 7.0
    sampler: str = "euler"
    scheduler: str = "normal"
    model: str = "sdxl"
    params: dict = field(default_factory=dict)


@dataclass
class GenerationResult:
    image_bytes: bytes
    width: int
    height: int
    seed: int
    backend: str
    duration_seconds: float
