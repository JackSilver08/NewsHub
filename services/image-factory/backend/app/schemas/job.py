"""Pydantic request/response schemas for jobs and images."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.schemas.creative import CreativeBriefInput


class GenerationParams(BaseModel):
    negative_prompt: str = ""
    seed: int | None = None
    width: int = 1024
    height: int = 1024
    steps: int | None = None
    cfg: float | None = None
    sampler: str | None = None
    scheduler: str | None = None
    model: str | None = None


class CreateJobRequest(BaseModel):
    prompt: str = Field(default="", max_length=8000)
    quantity: int = Field(default=1, ge=1, le=64)
    params: GenerationParams = Field(default_factory=GenerationParams)
    creative: CreativeBriefInput | None = None

    @model_validator(mode="after")
    def require_prompt_or_creative(self):
        if not self.prompt.strip() and self.creative is None:
            raise ValueError("A prompt or creative brief is required")
        return self


class JobItemOut(BaseModel):
    id: str
    item_index: int
    prompt: str
    negative_prompt: str | None
    seed: int | None
    width: int
    height: int
    status: str
    attempts: int
    error_message: str | None
    source_row_number: int | None

    class Config:
        from_attributes = True


class JobOut(BaseModel):
    id: str
    user_id: str
    source_type: str
    status: str
    total_items: int
    completed_items: int
    failed_items: int
    progress: float
    error_message: str | None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class JobDetailOut(JobOut):
    items: list[JobItemOut] = []


class ImageOut(BaseModel):
    id: str
    job_id: str
    job_item_id: str
    user_id: str
    file_path: str
    thumbnail_path: str | None
    seed: int | None
    width: int | None
    height: int | None
    file_size: int | None
    status: str
    metadata_json: str | None = None
    created_at: str

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    message: str


class CsvPreviewRow(BaseModel):
    row_number: int
    data: dict
    valid: bool
    error: str | None = None


class CsvPreviewOut(BaseModel):
    total_rows: int
    valid_rows: int
    total_images: int
    errors: int
    rows: list[CsvPreviewRow]
    fieldnames: list[str]
