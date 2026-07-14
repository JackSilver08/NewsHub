"""Persisted application settings stored in the `settings` table as JSON.

These are runtime-editable limits/defaults, seeded from config on first read.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings as cfg
from app.core.utils import utcnow_iso
from app.models import Setting

DEFAULTS: dict = {
    "max_pending_jobs_per_user": cfg.max_pending_jobs_per_user,
    "max_images_per_request": cfg.max_images_per_request,
    "max_csv_rows": cfg.max_csv_rows,
    "max_resolution": cfg.max_resolution,
    "allowed_resolutions": sorted(cfg.allowed_resolution_set),
    "default_model": cfg.default_model,
    "default_steps": cfg.default_steps,
    "default_cfg": cfg.default_cfg,
    "default_sampler": cfg.default_sampler,
    "default_scheduler": cfg.default_scheduler,
    "default_width": cfg.default_width,
    "default_height": cfg.default_height,
    "comfyui_enabled": cfg.comfyui_enabled,
    # Optional LLM for turning articles into image prompts (OpenAI-compatible;
    # defaults target a local Ollama server). Disabled by default -> offline
    # heuristic is used.
    "prompt_llm_enabled": False,
    "prompt_llm_base_url": "http://localhost:11434/v1",
    "prompt_llm_model": "qwen2.5:3b",
    "prompt_llm_api_key": "",
}


def get_all(db: Session) -> dict:
    rows = db.scalars(select(Setting)).all()
    stored = {r.key: json.loads(r.value_json) for r in rows}
    merged = {**DEFAULTS, **stored}
    return merged


def get_value(db: Session, key: str):
    row = db.get(Setting, key)
    if row is None:
        return DEFAULTS.get(key)
    return json.loads(row.value_json)


def set_values(db: Session, updates: dict) -> dict:
    now = utcnow_iso()
    for key, value in updates.items():
        row = db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value_json=json.dumps(value), updated_at=now))
        else:
            row.value_json = json.dumps(value)
            row.updated_at = now
    db.commit()
    return get_all(db)
