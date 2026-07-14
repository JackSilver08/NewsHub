"""CSV batch endpoints (plan section 8, 11)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.core.utils import job_folder_name
from app.db.base import get_db
from app.models import Job
from app.schemas.job import CsvPreviewOut, JobOut
from app.services import csv_service, job_service
from app.services.job_service import QuotaError
from app.storage.manager import storage

router = APIRouter(prefix="/api/batches", tags=["batches"])


@router.post("/csv/preview", response_model=CsvPreviewOut)
async def preview_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    raw = await file.read()
    try:
        return csv_service.parse_and_validate(raw, db, file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/csv", response_model=JobOut)
async def create_csv_batch(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    raw = await file.read()
    try:
        job = job_service.create_csv_job(db, user_id, raw, file.filename)
    except QuotaError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return job


@router.get("/{job_id}/report.csv")
def report_csv(job_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    job = db.get(Job, job_id)
    if job is None or job.user_id != user_id:
        raise HTTPException(status_code=404, detail="Job not found")
    folder = job_folder_name(job.created_at, job.id.split("_")[-1])
    path: Path = storage.job_dir(job.user_id, folder) / "result.csv"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report not generated yet")
    return FileResponse(path, media_type="text/csv", filename=f"{job.id}_report.csv")
