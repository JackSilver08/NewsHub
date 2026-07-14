"""Job orchestration: create prompt/CSV jobs, enforce quotas, and manage
lifecycle (pause/resume/cancel/retry). See plan sections 6, 7, 8.
"""

from __future__ import annotations

import json
import random

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.core.utils import new_id, utcnow_iso
from app.models import Image, Job, JobItem
from app.schemas.job import CreateJobRequest
from app.services import creative_director, csv_service, prompt_builder, settings_service
from app.services.events import bus
from app.services.csv_service import _safe_int

logger = get_logger(__name__)

ACTIVE_JOB_STATUSES = ("pending", "queued", "running", "paused")


def _slim(data: dict) -> dict:
    """Drop bulky free-text content columns before storing per-item params."""
    return {k: v for k, v in data.items() if k not in csv_service.CONTENT_KEYS}


class QuotaError(Exception):
    pass


def _check_pending_quota(db: Session, user_id: str) -> None:
    limit = settings_service.get_value(db, "max_pending_jobs_per_user") or settings.max_pending_jobs_per_user
    count = db.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.user_id == user_id, Job.status.in_(("pending", "queued", "running", "paused")))
    )
    if count is not None and count >= limit:
        raise QuotaError(f"You already have {count} active jobs (limit {limit}).")


def _resolve_defaults(db: Session, params: dict) -> dict:
    def d(key):
        return settings_service.get_value(db, key)

    return {
        "model": params.get("model") or d("default_model"),
        "steps": params.get("steps") if params.get("steps") is not None else d("default_steps"),
        "cfg": params.get("cfg") if params.get("cfg") is not None else d("default_cfg"),
        "sampler": params.get("sampler") or d("default_sampler"),
        "scheduler": params.get("scheduler") or d("default_scheduler"),
        "negative_prompt": params.get("negative_prompt") or "",
    }


def create_prompt_job(db: Session, user_id: str, req: CreateJobRequest) -> Job:
    _check_pending_quota(db, user_id)

    max_images = settings_service.get_value(db, "max_images_per_request") or settings.max_images_per_request
    if req.quantity > max_images:
        raise QuotaError(f"Quantity {req.quantity} exceeds max of {max_images} per request.")

    now = utcnow_iso()
    job_id = new_id("job")
    p = req.params.model_dump()
    creative_package = None
    prompt = req.prompt.strip()
    source_type = "prompt"

    if req.creative is not None:
        creative_package = creative_director.build_creative_package(
            req.creative,
            db,
            user_negative=p.get("negative_prompt") or "",
        )
        prompt = creative_package.compiled_prompt
        p.update(
            {
                "width": creative_package.width,
                "height": creative_package.height,
                "steps": creative_package.steps,
                "cfg": creative_package.cfg,
            }
        )
        source_type = "creative"

    defaults = _resolve_defaults(db, p)

    if creative_package is not None:
        defaults["negative_prompt"] = creative_package.negative_prompt

    width = p.get("width") or settings_service.get_value(db, "default_width")
    height = p.get("height") or settings_service.get_value(db, "default_height")
    _validate_resolution(db, width, height, allow_custom_canvas=creative_package is not None)

    stored_params = {**p, **defaults}
    if creative_package is not None and req.creative is not None:
        stored_params.update(
            {
                "creative": req.creative.model_dump(),
                "creative_package": creative_package.model_dump(),
                "user_prompt": req.prompt.strip(),
            }
        )
    params_json = json.dumps(stored_params, ensure_ascii=False)
    job = Job(
        id=job_id,
        user_id=user_id,
        source_type=source_type,
        status="queued",
        total_items=req.quantity,
        params_json=params_json,
        created_at=now,
        updated_at=now,
    )
    db.add(job)

    base_seed = p.get("seed")
    for i in range(req.quantity):
        seed = base_seed + i if base_seed is not None else random.randint(1, 2**31 - 1)
        item = JobItem(
            id=new_id("item"),
            job_id=job_id,
            item_index=i,
            prompt=prompt,
            negative_prompt=defaults["negative_prompt"],
            seed=seed,
            width=width,
            height=height,
            status="queued",
            dedupe_key=f"{job_id}:{i}",
            params_json=params_json,
            created_at=now,
            updated_at=now,
        )
        db.add(item)

    db.commit()
    bus.publish("job_progress", _job_event(job))
    logger.info("Created prompt job %s with %d items", job_id, req.quantity)
    return job


def create_csv_job(db: Session, user_id: str, raw: bytes, filename: str | None = None) -> Job:
    _check_pending_quota(db, user_id)

    now = utcnow_iso()
    job_id = new_id("job")
    default_w = settings_service.get_value(db, "default_width")
    default_h = settings_service.get_value(db, "default_height")

    job = Job(
        id=job_id,
        user_id=user_id,
        source_type="csv",
        status="queued",
        total_items=0,
        created_at=now,
        updated_at=now,
    )
    db.add(job)

    item_index = 0
    for row_number, data in csv_service.iter_valid_rows(raw, db, filename):
        row_id = str(data.get("id") or row_number)
        quantity = max(1, _safe_int(data.get("quantity"), 1))
        base_seed = _safe_int(data.get("seed"), None) if data.get("seed") else None
        width = _safe_int(data.get("width"), default_w)
        height = _safe_int(data.get("height"), default_h)
        defaults = _resolve_defaults(db, data)

        # Prompt: use the explicit column, else auto-generate from content text.
        prompt = (data.get("prompt") or "").strip()
        if not prompt:
            content = csv_service.get_content(data)
            if content:
                prompt = prompt_builder.build_prompt(content)["prompt"]
        if not prompt:
            continue  # nothing to generate from this row

        for q in range(quantity):
            seed = base_seed + q if base_seed is not None else random.randint(1, 2**31 - 1)
            db.add(
                JobItem(
                    id=new_id("item"),
                    job_id=job_id,
                    source_row_number=row_number,
                    source_row_id=row_id,
                    item_index=item_index,
                    prompt=prompt,
                    negative_prompt=defaults["negative_prompt"],
                    seed=seed,
                    width=width,
                    height=height,
                    status="queued",
                    dedupe_key=f"{job_id}:{row_number}:{q}",
                    params_json=json.dumps({**_slim(data), **defaults}),
                    created_at=now,
                    updated_at=now,
                )
            )
            item_index += 1

    if item_index == 0:
        db.rollback()
        raise ValueError("No valid rows found in CSV.")

    job.total_items = item_index
    db.commit()
    bus.publish("job_progress", _job_event(job))
    logger.info("Created CSV job %s with %d items", job_id, item_index)
    return job


def _validate_resolution(
    db: Session,
    width: int,
    height: int,
    *,
    allow_custom_canvas: bool = False,
) -> None:
    max_res = settings_service.get_value(db, "max_resolution") or settings.max_resolution
    allowed = set(settings_service.get_value(db, "allowed_resolutions") or [])
    for label, value in (("width", width), ("height", height)):
        if value > max_res:
            raise QuotaError(f"{label} {value} exceeds max resolution {max_res}")
        if value < 256 or value % 8 != 0:
            raise QuotaError(f"{label} must be at least 256 and divisible by 8")
        if allowed and value not in allowed and not allow_custom_canvas:
            raise QuotaError(f"{label} {value} not in allowed resolutions {sorted(allowed)}")


# --- lifecycle -------------------------------------------------------

def pause_job(db: Session, job: Job) -> Job:
    if job.status in ("running", "queued", "pending"):
        job.status = "paused"
        job.updated_at = utcnow_iso()
        db.query(JobItem).filter(
            JobItem.job_id == job.id, JobItem.status == "queued"
        ).update({"status": "paused", "updated_at": utcnow_iso()})
        db.commit()
        bus.publish("job_progress", _job_event(job))
    return job


def resume_job(db: Session, job: Job) -> Job:
    if job.status == "paused":
        job.status = "queued"
        job.updated_at = utcnow_iso()
        db.query(JobItem).filter(
            JobItem.job_id == job.id, JobItem.status == "paused"
        ).update({"status": "queued", "updated_at": utcnow_iso()})
        db.commit()
        bus.publish("job_progress", _job_event(job))
    return job


def cancel_job(db: Session, job: Job) -> Job:
    if job.status in ("completed", "cancelled"):
        return job
    job.status = "cancelled"
    job.updated_at = utcnow_iso()
    db.query(JobItem).filter(
        JobItem.job_id == job.id, JobItem.status.in_(("queued", "paused"))
    ).update({"status": "cancelled", "updated_at": utcnow_iso()})
    db.commit()
    bus.publish("job_progress", _job_event(job))
    return job


def retry_failed(db: Session, job: Job) -> Job:
    updated = db.query(JobItem).filter(
        JobItem.job_id == job.id, JobItem.status == "failed"
    ).update({"status": "queued", "attempts": 0, "error_message": None, "updated_at": utcnow_iso()})
    if updated:
        job.status = "queued"
        job.failed_items = 0
        job.error_message = None
        job.updated_at = utcnow_iso()
        db.commit()
        bus.publish("job_progress", _job_event(job))
    return job


def recompute_job_progress(db: Session, job_id: str) -> None:
    job = db.get(Job, job_id)
    if job is None:
        return
    counts = dict(
        db.execute(
            select(JobItem.status, func.count()).where(JobItem.job_id == job_id).group_by(JobItem.status)
        ).all()
    )
    completed = counts.get("completed", 0)
    failed = counts.get("failed", 0)
    cancelled = counts.get("cancelled", 0)
    total = job.total_items or sum(counts.values())
    job.completed_items = completed
    job.failed_items = failed
    finished = completed + failed + cancelled
    job.progress = round(finished / total, 4) if total else 0.0
    job.updated_at = utcnow_iso()

    if job.status not in ("paused", "cancelled"):
        remaining = counts.get("queued", 0) + counts.get("running", 0)
        if remaining == 0 and finished >= total:
            job.status = "completed" if failed == 0 else ("completed" if completed > 0 else "failed")
    db.commit()
    bus.publish("job_progress", _job_event(job))


def _job_event(job: Job) -> dict:
    return {
        "id": job.id,
        "status": job.status,
        "progress": job.progress,
        "completed_items": job.completed_items,
        "failed_items": job.failed_items,
        "total_items": job.total_items,
    }
