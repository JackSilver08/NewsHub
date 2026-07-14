"""Prompt helper endpoints: build an image prompt from long article text."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services import prompt_builder

router = APIRouter(prefix="/api/prompt", tags=["prompt"])


class FromTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50000)


class FromTextResponse(BaseModel):
    prompt: str
    source: str  # "llm" | "heuristic"


@router.post("/from-text", response_model=FromTextResponse)
def from_text(req: FromTextRequest):
    result = prompt_builder.build_prompt(req.text)
    return FromTextResponse(**result)
