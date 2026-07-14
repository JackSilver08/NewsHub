"""Create tables and seed baseline rows (default user, default settings).

For the MVP we create the schema directly from the ORM metadata. Alembic can be
introduced later (plan section 10) once the schema stabilises.
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import get_logger
from app.core.utils import new_id, utcnow_iso
from app.db.base import Base, SessionLocal, engine
from app.models import User  # noqa: F401  (import registers metadata)
import app.models  # noqa: F401

logger = get_logger(__name__)

DEFAULT_USER_ID = "user_local"
DEFAULT_USERNAME = "local"


def init_db() -> None:
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    (settings.storage_root / "users").mkdir(exist_ok=True)
    (settings.storage_root / "temp").mkdir(exist_ok=True)
    (settings.storage_root / "models").mkdir(exist_ok=True)
    (settings.storage_root / "logs").mkdir(exist_ok=True)

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.id == DEFAULT_USER_ID))
        if existing is None:
            db.add(
                User(
                    id=DEFAULT_USER_ID,
                    username=DEFAULT_USERNAME,
                    role="admin",
                    created_at=utcnow_iso(),
                )
            )
            db.commit()
            logger.info("Seeded default user '%s'", DEFAULT_USERNAME)

    logger.info("Database initialised at %s", settings.database_url)
