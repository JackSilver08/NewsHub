"""System status endpoints: hardware, storage, GPU, worker health."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.comfyui.client import make_generator
from app.core.config import settings
from app.core.hardware import detect_hardware
from app.db.base import get_db
from app.models import Image, Job, JobItem, WorkerHeartbeat
from app.storage.manager import storage

router = APIRouter(prefix="/api/system", tags=["system"])

_hw_cache: dict = {}


@router.get("/status")
def system_status(db: Session = Depends(get_db)):
    heartbeats = db.scalars(select(WorkerHeartbeat)).all()
    queued = db.scalar(select(func.count()).select_from(JobItem).where(JobItem.status == "queued")) or 0
    running = db.scalar(select(func.count()).select_from(JobItem).where(JobItem.status == "running")) or 0
    active_jobs = db.scalar(
        select(func.count()).select_from(Job).where(Job.status.in_(("queued", "running", "paused")))
    ) or 0
    return {
        "comfyui_enabled": settings.comfyui_enabled,
        "backend": "comfyui" if settings.comfyui_enabled else "mock",
        "queue": {"queued_items": queued, "running_items": running, "active_jobs": active_jobs},
        "workers": [
            {
                "worker_id": h.worker_id,
                "gpu_id": h.gpu_id,
                "status": h.status,
                "current_job_item_id": h.current_job_item_id,
                "last_seen_at": h.last_seen_at,
            }
            for h in heartbeats
        ],
    }


@router.get("/hardware")
def hardware(refresh: bool = False):
    if refresh or "info" not in _hw_cache:
        _hw_cache["info"] = detect_hardware().to_dict()
    return _hw_cache["info"]


@router.get("/gpu")
def gpu():
    info = detect_hardware()
    return {"has_nvidia_gpu": info.has_nvidia_gpu, "cuda_available": info.cuda_available, "gpus": [g.__dict__ for g in info.gpus]}


@router.get("/storage")
def storage_status(db: Session = Depends(get_db)):
    total_images = db.scalar(select(func.count()).select_from(Image)) or 0
    return {
        "storage_root": str(settings.storage_root),
        "disk_free_gb": round(storage.disk_free_bytes() / 1024**3, 2),
        "min_free_gb": round(settings.min_free_disk_bytes / 1024**3, 2),
        "total_images": total_images,
    }


@router.get("/comfyui/health")
def comfyui_health():
    gen = make_generator()
    healthy = gen.health_check() if hasattr(gen, "health_check") else True
    return {"backend": getattr(gen, "backend_name", "unknown"), "healthy": healthy}
