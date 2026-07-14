"""Creative briefing, style preset, and brand-asset endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import UnidentifiedImageError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user_id
from app.core.utils import new_id
from app.db.base import get_db
from app.schemas.creative import (
    CreativeBriefInput,
    CreativePackageOut,
    LogoAssetOut,
    StylePresetOut,
)
from app.services.creative_director import build_creative_package
from app.services.style_presets import public_styles
from app.storage.manager import storage

router = APIRouter(prefix="/api/creative", tags=["creative"])


@router.get("/styles", response_model=list[StylePresetOut])
def list_styles():
    return public_styles()


@router.post("/briefs/preview", response_model=CreativePackageOut)
def preview_brief(req: CreativeBriefInput, db: Session = Depends(get_db)):
    return build_creative_package(req, db)


@router.post("/assets/logo", response_model=LogoAssetOut)
async def upload_logo(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=422, detail="Logo file is empty")
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Logo must be 5 MB or smaller")
    asset_id = new_id("logo")
    try:
        storage.save_logo_asset(user_id=user_id, asset_id=asset_id, data=data)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid logo image: {exc}") from exc
    return LogoAssetOut(id=asset_id, filename=file.filename or "logo.png")
