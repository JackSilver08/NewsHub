"""Tabular (CSV/Excel) parsing and validation for batch generation (plan section 8).

Accepts either a `prompt` column or a free-text content column
(`content`/`article`/`noi_dung`/`nội dung`). When only content is present, the
prompt is generated automatically at job-creation time (see job_service).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.job import CsvPreviewOut, CsvPreviewRow
from app.services import settings_service, tabular_importer

# A row must contain an id and at least one of: a prompt, or a content column.
REQUIRED_ID = "id"
CONTENT_KEYS = ("content", "article", "noi_dung", "nội dung", "noidung", "bai_viet", "bài viết")
OPTIONAL_HEADERS = {
    "negative_prompt", "seed", "width", "height", "quantity",
    "model", "steps", "cfg", "sampler", "scheduler",
}


def get_content(data: dict) -> str:
    for key in CONTENT_KEYS:
        val = (data.get(key) or "").strip()
        if val:
            return val
    return ""


def parse_and_validate(
    raw: bytes, db: Session, filename: str | None = None, preview_limit: int = 100
) -> CsvPreviewOut:
    fieldnames, all_rows = tabular_importer.read_rows(filename, raw)

    if REQUIRED_ID not in fieldnames:
        raise ValueError("Thiếu cột bắt buộc: 'id'")
    has_prompt_col = "prompt" in fieldnames
    has_content_col = any(k in fieldnames for k in CONTENT_KEYS)
    if not (has_prompt_col or has_content_col):
        raise ValueError("Cần có cột 'prompt' hoặc cột nội dung ('content'/'noi_dung')")

    allowed_res = set(settings_service.get_value(db, "allowed_resolutions") or [])
    max_res = settings_service.get_value(db, "max_resolution") or settings.max_resolution
    max_rows = settings_service.get_value(db, "max_csv_rows") or settings.max_csv_rows

    if len(all_rows) > max_rows:
        raise ValueError(f"File vượt quá tối đa {max_rows} dòng")

    rows: list[CsvPreviewRow] = []
    valid_rows = 0
    total_images = 0
    errors = 0

    for idx, data in enumerate(all_rows, start=1):
        error = _validate_row(data, allowed_res, max_res)
        quantity = _safe_int(data.get("quantity"), default=1)

        if error is None:
            valid_rows += 1
            total_images += max(1, quantity)
        else:
            errors += 1

        if len(rows) < preview_limit:
            # For preview, show whether the prompt is auto-generated from content.
            preview_data = dict(data)
            if not (data.get("prompt") or "").strip() and get_content(data):
                preview_data["prompt"] = "(tự tạo từ nội dung)"
            rows.append(
                CsvPreviewRow(row_number=idx, data=preview_data, valid=error is None, error=error)
            )

    return CsvPreviewOut(
        total_rows=len(all_rows),
        valid_rows=valid_rows,
        total_images=total_images,
        errors=errors,
        rows=rows,
        fieldnames=fieldnames,
    )


def iter_valid_rows(raw: bytes, db: Session, filename: str | None = None):
    """Yield (row_number, data) for rows that pass validation."""
    _fieldnames, all_rows = tabular_importer.read_rows(filename, raw)
    allowed_res = set(settings_service.get_value(db, "allowed_resolutions") or [])
    max_res = settings_service.get_value(db, "max_resolution") or settings.max_resolution
    for idx, data in enumerate(all_rows, start=1):
        if _validate_row(data, allowed_res, max_res) is None:
            yield idx, data


def _validate_row(data: dict, allowed_res: set, max_res: int) -> str | None:
    prompt = (data.get("prompt") or "").strip()
    content = get_content(data)
    if not prompt and not content:
        return "Thiếu prompt và nội dung"

    seed = data.get("seed")
    if seed not in (None, "") and not _is_int(seed):
        return "Seed phải là số nguyên"

    for dim in ("width", "height"):
        value = data.get(dim)
        if value not in (None, ""):
            if not _is_int(value):
                return f"{dim} phải là số nguyên"
            n = int(value)
            if allowed_res and n not in allowed_res:
                return f"{dim} {n} không thuộc kích thước cho phép {sorted(allowed_res)}"
            if n > max_res:
                return f"{dim} vượt quá {max_res}"

    quantity = data.get("quantity")
    if quantity not in (None, ""):
        if not _is_int(quantity):
            return "quantity phải là số nguyên"
        if int(quantity) < 1:
            return "quantity phải >= 1"

    return None


def _is_int(value) -> bool:
    try:
        int(str(value).strip())
        return True
    except (ValueError, TypeError):
        return False


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (ValueError, TypeError, AttributeError):
        return default
