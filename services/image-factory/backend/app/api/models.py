"""Model registry endpoints (plan sections 5, 11).

MVP: list registered models and scan the models directory for known extensions.
Full license workflow is future work.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.utils import new_id, utcnow_iso
from app.db.base import get_db
from app.models import Model

router = APIRouter(prefix="/api/models", tags=["models"])

_SCAN_EXTENSIONS = {".safetensors", ".ckpt", ".gguf", ".pt"}


@router.get("")
def list_models(db: Session = Depends(get_db)):
    rows = db.scalars(select(Model)).all()
    return [
        {
            "id": m.id,
            "name": m.name,
            "type": m.type,
            "path": m.path,
            "hash": m.hash,
            "status": m.status,
            "license_id": m.license_id,
        }
        for m in rows
    ]


@router.post("/scan")
def scan_models(db: Session = Depends(get_db)):
    """Scan storage/models for checkpoint files and register new ones.

    Prefers .safetensors and skips pickle-based formats by default (plan section 14).
    """
    models_dir = settings.storage_root / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    known_paths = {m.path for m in db.scalars(select(Model)).all()}

    added = []
    for path in models_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in _SCAN_EXTENSIONS:
            continue
        str_path = str(path)
        if str_path in known_paths:
            continue
        model = Model(
            id=new_id("model"),
            name=path.stem,
            type="checkpoint",
            path=str_path,
            status="active" if path.suffix.lower() == ".safetensors" else "review",
            created_at=utcnow_iso(),
        )
        db.add(model)
        added.append(path.name)
    if added:
        db.commit()
    return {"added": added, "count": len(added)}
