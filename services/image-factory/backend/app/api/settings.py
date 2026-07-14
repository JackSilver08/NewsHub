"""Runtime settings endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.services import settings_service

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    return settings_service.get_all(db)


@router.put("")
def update_settings(updates: dict, db: Session = Depends(get_db)):
    return settings_service.set_values(db, updates)
