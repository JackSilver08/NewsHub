"""Small shared helpers: IDs and timestamps."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


def new_id(prefix: str = "") -> str:
    uid = uuid.uuid4().hex
    return f"{prefix}_{uid}" if prefix else uid


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        cleaned = value.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def job_folder_name(created_iso: str, short_id: str) -> str:
    """Build a stable, filesystem-safe job folder like job_20260710_ab12cd."""
    dt = parse_iso(created_iso) or datetime.now(timezone.utc)
    return f"job_{dt.strftime('%Y%m%d_%H%M%S')}_{short_id[:6]}"
