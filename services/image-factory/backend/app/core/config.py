"""Application configuration.

All settings can be overridden via environment variables or a `.env` file.
Defaults are safe for a single-user local install on Windows.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> project root is three parents up from this file's
# parent (app/core -> app -> backend -> root).
BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent

_FROZEN = getattr(sys, "frozen", False)

# BASE_DIR: writable location for runtime data (.env, storage, db).
#   - dev: project root
#   - frozen .exe: the folder containing the executable
BASE_DIR = Path(sys.executable).resolve().parent if _FROZEN else PROJECT_ROOT

# RESOURCE_DIR: read-only bundled assets (frontend build, workflows).
#   - dev: project root
#   - frozen .exe: the PyInstaller temp extraction dir (_MEIPASS)
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT)) if _FROZEN else PROJECT_ROOT

# A local PyInstaller build lives in ``project/dist/AIImageFactory``. Reuse the
# project runtime config when the packaged folder has no private .env yet.
_ENV_FILE = BASE_DIR / ".env"
if _FROZEN and not _ENV_FILE.exists():
    workspace_env = BASE_DIR.parent.parent / ".env"
    if workspace_env.exists():
        _ENV_FILE = workspace_env


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Server ---
    host: str = "127.0.0.1"
    port: int = 8000
    # Comma separated list of allowed CORS origins for the Vue dev server.
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:4321,http://127.0.0.1:4321,"
        "https://newshub-jack.netlify.app"
    )

    # --- Paths ---
    storage_root: Path = BASE_DIR / "storage"
    database_url: str = f"sqlite:///{(BASE_DIR / 'storage' / 'app.db').as_posix()}"

    # --- ComfyUI ---
    # When comfyui_enabled is False the worker uses a built-in mock generator that
    # produces placeholder images. This lets the whole pipeline be exercised without
    # a GPU or a running ComfyUI instance.
    comfyui_enabled: bool = False
    comfyui_base_url: str = "http://127.0.0.1:8188"
    comfyui_workflow: str = "sdxl_basic_api.json"
    comfyui_timeout_seconds: int = 600

    # --- Worker / queue ---
    worker_id: str = "worker-1"
    gpu_id: str = "0"
    lock_timeout_seconds: int = 900
    heartbeat_interval_seconds: int = 10
    poll_interval_seconds: float = 1.0
    max_retries: int = 2

    # --- Limits (see plan section 6) ---
    max_pending_jobs_per_user: int = 2
    max_images_per_request: int = 4
    max_csv_rows: int = 600
    max_csv_bytes: int = 5 * 1024 * 1024
    max_resolution: int = 1024
    allowed_resolutions: str = "512,768,1024"

    # --- Defaults for generation ---
    default_model: str = "sdxl"
    default_steps: int = 25
    default_cfg: float = 7.0
    default_sampler: str = "euler"
    default_scheduler: str = "normal"
    default_width: int = 1024
    default_height: int = 1024

    # --- Disk guard ---
    min_free_disk_bytes: int = 2 * 1024 * 1024 * 1024  # 2 GB

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_resolution_set(self) -> set[int]:
        return {int(r.strip()) for r in self.allowed_resolutions.split(",") if r.strip()}

    @property
    def workflows_dir(self) -> Path:
        return RESOURCE_DIR / "workflows"

    @property
    def frontend_dist(self) -> Path:
        return RESOURCE_DIR / "frontend" / "dist"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
