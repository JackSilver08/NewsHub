"""Job endpoints (plan section 11)."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.base import get_db
from app.models import Image, Job
from app.schemas.job import (
    CreateJobRequest,
    JobDetailOut,
    JobOut,
    MessageOut,
)
from app.core.utils import job_folder_name
from app.services import job_service
from app.services.job_service import QuotaError
from app.storage.manager import storage

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _get_job_or_404(db: Session, job_id: str, user_id: str) -> Job:
    job = db.get(Job, job_id)
    if job is None or job.user_id != user_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("", response_model=JobOut)
def create_job(
    req: CreateJobRequest,
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        job = job_service.create_prompt_job(db, user_id, req)
    except QuotaError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    return job


@router.get("", response_model=list[JobOut])
def list_jobs(
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    stmt = select(Job).where(Job.user_id == user_id)
    if status:
        stmt = stmt.where(Job.status == status)
    stmt = stmt.order_by(Job.created_at.desc()).limit(limit)
    return list(db.scalars(stmt).all())


@router.get("/{job_id}", response_model=JobDetailOut)
def get_job(job_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    job = _get_job_or_404(db, job_id, user_id)
    return job


@router.post("/{job_id}/pause", response_model=JobOut)
def pause(job_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return job_service.pause_job(db, _get_job_or_404(db, job_id, user_id))


@router.post("/{job_id}/resume", response_model=JobOut)
def resume(job_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return job_service.resume_job(db, _get_job_or_404(db, job_id, user_id))


@router.post("/{job_id}/cancel", response_model=JobOut)
def cancel(job_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    job = job_service.cancel_job(db, _get_job_or_404(db, job_id, user_id))
    from app.workers.worker import worker

    worker.interrupt_job(job.id)
    return job


@router.post("/{job_id}/retry-failed", response_model=JobOut)
def retry_failed(job_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return job_service.retry_failed(db, _get_job_or_404(db, job_id, user_id))


@router.post("/{job_id}/open-folder", response_model=MessageOut)
def open_folder(job_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    """Open this job's output folder in the OS file manager (local desktop app)."""
    job = _get_job_or_404(db, job_id, user_id)
    folder_name = job_folder_name(job.created_at, job.id.split("_")[-1])
    folder = storage.job_dir(job.user_id, folder_name)
    if not folder.exists():
        raise HTTPException(status_code=404, detail="Folder not created yet (no images generated)")
    try:
        opened = storage.reveal(folder, select=False)
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MessageOut(message=f"Opened {opened}")


@router.get("/{job_id}/download.zip")
def download_zip(job_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    job = _get_job_or_404(db, job_id, user_id)
    images = db.scalars(
        select(Image).where(Image.job_id == job.id, Image.status == "completed")
    ).all()
    if not images:
        raise HTTPException(status_code=404, detail="No completed images to download")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for img in images:
            path = Path(img.file_path)
            if path.exists() and not path.is_symlink():
                zf.write(path, arcname=path.name)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{job.id}.zip"'},
    )
