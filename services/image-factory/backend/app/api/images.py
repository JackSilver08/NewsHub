"""Image endpoints: list, detail, serve file/thumbnail, delete."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.db.base import get_db
from app.models import Image
from app.schemas.job import ImageOut, MessageOut
from app.storage.manager import storage

router = APIRouter(prefix="/api/images", tags=["images"])


def _get_image(db: Session, image_id: str, user_id: str) -> Image:
    img = db.get(Image, image_id)
    if img is None or img.user_id != user_id:
        raise HTTPException(status_code=404, detail="Image not found")
    return img


@router.get("", response_model=list[ImageOut])
def list_images(
    job_id: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    stmt = select(Image).where(Image.user_id == user_id, Image.status == "completed")
    if job_id:
        stmt = stmt.where(Image.job_id == job_id)
    stmt = stmt.order_by(Image.created_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


@router.get("/{image_id}", response_model=ImageOut)
def get_image(image_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    return _get_image(db, image_id, user_id)


@router.get("/{image_id}/file")
def get_image_file(image_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    img = _get_image(db, image_id, user_id)
    path = Path(img.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(path)


@router.get("/{image_id}/thumbnail")
def get_thumbnail(image_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    img = _get_image(db, image_id, user_id)
    path = Path(img.thumbnail_path) if img.thumbnail_path else Path(img.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail missing")
    return FileResponse(path)


@router.delete("/{image_id}", response_model=MessageOut)
def delete_image(image_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    img = _get_image(db, image_id, user_id)
    storage.delete_image_files(img.file_path, img.thumbnail_path)
    db.delete(img)
    db.commit()
    return MessageOut(message="Image deleted")


@router.post("/{image_id}/reveal", response_model=MessageOut)
def reveal_image(image_id: str, db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)):
    """Open the containing folder in the OS file manager and select the image.

    Only meaningful on the local machine running the desktop app.
    """
    img = _get_image(db, image_id, user_id)
    try:
        folder = storage.reveal(img.file_path, select=True)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File missing on disk") from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MessageOut(message=f"Opened {folder}")
