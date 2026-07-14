"""FastAPI application entrypoint.

Starts the background worker in the app lifespan, mounts the API routers, and
serves a health endpoint. Bind defaults to 127.0.0.1 for safety (plan section 14).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import (
    batches,
    creative,
    events,
    images,
    jobs,
    models,
    prompt,
    settings as settings_api,
    system,
)
from app.core.config import settings
from app.core.hardware import detect_hardware
from app.core.logging import get_logger, setup_logging
from app.db.init_db import init_db
from app.workers.worker import worker

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Image Factory v%s", __version__)
    init_db()

    hw = detect_hardware()
    logger.info(
        "Hardware: %s | RAM %.1fGB | GPU: %s | recommended model: %s",
        hw.os,
        hw.ram_total_gb,
        ", ".join(g.name for g in hw.gpus) or "none",
        hw.recommended_model,
    )
    for warning in hw.warnings:
        logger.warning(warning)

    worker.start()
    try:
        yield
    finally:
        worker.stop()
        logger.info("Shutdown complete")


app = FastAPI(title="AI Image Factory", version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(batches.router)
app.include_router(images.router)
app.include_router(models.router)
app.include_router(system.router)
app.include_router(settings_api.router)
app.include_router(prompt.router)
app.include_router(creative.router)
app.include_router(events.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": __version__, "backend": "comfyui" if settings.comfyui_enabled else "mock"}


# --- Serve the built Vue frontend (desktop / single-server mode) ------------
# When frontend/dist exists, the API and UI share one origin so no Vite dev
# server or CORS is needed. API routers above take priority; the catch-all
# below returns index.html for SPA deep links.
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

_frontend_dist = settings.frontend_dist
if _frontend_dist.exists():
    _assets = _frontend_dist / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            return FileResponse(_frontend_dist / "index.html", status_code=404)
        candidate = _frontend_dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_frontend_dist / "index.html")

    logger.info("Serving bundled frontend from %s", _frontend_dist)
else:
    logger.info("No frontend build found (%s); run 'npm run build' for desktop mode", _frontend_dist)
