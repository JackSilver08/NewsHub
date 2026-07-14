"""File storage manager (plan section 9).

Responsibilities:
- Build safe, deterministic paths from internal IDs (never from user filenames).
- Guard every path against traversal outside the storage root.
- Save generated images, create WebP thumbnails, and maintain metadata.json.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image as PILImage

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Windows-invalid characters and reserved device names (plan section 9).
_INVALID_CHARS = set('<>:"/\\|?*')
_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

THUMBNAIL_MAX = 384


@dataclass
class SavedImage:
    file_path: Path
    thumbnail_path: Path
    width: int
    height: int
    file_size: int


def _sanitize_component(name: str) -> str:
    """Sanitise a single path component built from internal IDs."""
    cleaned = "".join("_" if c in _INVALID_CHARS else c for c in name)
    cleaned = cleaned.strip(" .")
    if cleaned.upper().split(".")[0] in _RESERVED_NAMES:
        cleaned = f"_{cleaned}"
    return cleaned or "_"


def _resolve_within_root(path: Path) -> Path:
    """Resolve `path` and ensure it stays inside the storage root."""
    root = settings.storage_root.resolve()
    resolved = path.resolve()
    if root != resolved and root not in resolved.parents:
        raise ValueError(f"Path escapes storage root: {resolved}")
    return resolved


class StorageManager:
    def __init__(self) -> None:
        self.root = settings.storage_root

    # --- path helpers -------------------------------------------------
    def job_dir(self, user_id: str, job_folder: str) -> Path:
        path = (
            self.root
            / "users"
            / _sanitize_component(user_id)
            / "jobs"
            / _sanitize_component(job_folder)
        )
        return _resolve_within_root(path)

    def ensure_job_dirs(self, user_id: str, job_folder: str) -> Path:
        base = self.job_dir(user_id, job_folder)
        (base / "original").mkdir(parents=True, exist_ok=True)
        (base / "thumbnails").mkdir(parents=True, exist_ok=True)
        return base

    def temp_dir(self) -> Path:
        path = self.root / "temp"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_logo_asset(self, *, user_id: str, asset_id: str, data: bytes) -> Path:
        """Validate and normalize an uploaded logo to a local RGBA PNG."""
        assets = _resolve_within_root(
            self.root / "users" / _sanitize_component(user_id) / "assets" / "logos"
        )
        assets.mkdir(parents=True, exist_ok=True)
        path = _resolve_within_root(assets / f"{_sanitize_component(asset_id)}.png")
        with PILImage.open(io.BytesIO(data)) as source:
            if source.width > 5000 or source.height > 5000:
                raise ValueError("Logo dimensions exceed 5000x5000")
            source.convert("RGBA").save(path, "PNG", optimize=True)
        return path

    def logo_asset_path(self, *, user_id: str, asset_id: str | None) -> Path | None:
        if not asset_id or _sanitize_component(asset_id) != asset_id:
            return None
        path = _resolve_within_root(
            self.root
            / "users"
            / _sanitize_component(user_id)
            / "assets"
            / "logos"
            / f"{asset_id}.png"
        )
        return path if path.exists() else None

    # --- image saving -------------------------------------------------
    def save_image_bytes(
        self,
        *,
        user_id: str,
        job_folder: str,
        filename: str,
        data: bytes,
    ) -> SavedImage:
        base = self.ensure_job_dirs(user_id, job_folder)
        safe_name = _sanitize_component(filename)
        original_path = _resolve_within_root(base / "original" / safe_name)

        with open(original_path, "wb") as f:
            f.write(data)

        with PILImage.open(io.BytesIO(data)) as img:
            width, height = img.size
            thumb = img.copy()
            thumb.thumbnail((THUMBNAIL_MAX, THUMBNAIL_MAX))
            thumb_name = safe_name.rsplit(".", 1)[0] + ".webp"
            thumbnail_path = _resolve_within_root(base / "thumbnails" / thumb_name)
            thumb.convert("RGB").save(thumbnail_path, "WEBP", quality=80)

        return SavedImage(
            file_path=original_path,
            thumbnail_path=thumbnail_path,
            width=width,
            height=height,
            file_size=original_path.stat().st_size,
        )

    def move_temp_file(
        self, *, user_id: str, job_folder: str, filename: str, temp_path: Path
    ) -> SavedImage:
        """Move a file produced by ComfyUI into the job's original folder."""
        temp_path = _resolve_within_root(temp_path) if self._is_in_root(temp_path) else temp_path.resolve()
        data = temp_path.read_bytes()
        saved = self.save_image_bytes(
            user_id=user_id, job_folder=job_folder, filename=filename, data=data
        )
        try:
            temp_path.unlink(missing_ok=True)
        except OSError as exc:  # noqa: BLE001
            logger.warning("Could not remove temp file %s: %s", temp_path, exc)
        return saved

    def _is_in_root(self, path: Path) -> bool:
        try:
            _resolve_within_root(path)
            return True
        except ValueError:
            return False

    # --- metadata -----------------------------------------------------
    def write_metadata(self, *, user_id: str, job_folder: str, metadata: dict) -> None:
        base = self.job_dir(user_id, job_folder)
        base.mkdir(parents=True, exist_ok=True)
        path = _resolve_within_root(base / "metadata.json")
        path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    def append_result_row(
        self, *, user_id: str, job_folder: str, row: dict, fieldnames: list[str]
    ) -> None:
        """Append a row to result.csv, escaping CSV-injection-prone cells."""
        import csv

        base = self.job_dir(user_id, job_folder)
        base.mkdir(parents=True, exist_ok=True)
        path = _resolve_within_root(base / "result.csv")
        write_header = not path.exists()
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerow({k: _escape_csv(str(row.get(k, ""))) for k in fieldnames})

    def delete_image_files(self, file_path: str, thumbnail_path: str | None) -> None:
        for p in (file_path, thumbnail_path):
            if not p:
                continue
            path = Path(p)
            if path.is_symlink():
                logger.warning("Refusing to delete symlink %s", path)
                continue
            if not self._is_in_root(path):
                logger.warning("Refusing to delete path outside storage root: %s", path)
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:  # noqa: BLE001
                logger.warning("Could not delete %s: %s", path, exc)

    def relative(self, path: Path | str) -> str:
        """Return a path relative to the storage root (for API responses)."""
        p = Path(path).resolve()
        try:
            return p.relative_to(self.root.resolve()).as_posix()
        except ValueError:
            return Path(path).as_posix()

    def disk_free_bytes(self) -> int:
        return shutil.disk_usage(str(self.root)).free

    # --- open in OS file manager --------------------------------------
    def reveal(self, path: Path | str, *, select: bool = True) -> Path:
        """Open the OS file manager at `path`.

        If `select` and the path is a file, the file is highlighted; otherwise the
        containing folder is opened. Only paths inside the storage root are allowed.
        Returns the folder that was opened.
        """
        p = Path(path)
        if not self._is_in_root(p):
            raise ValueError("Refusing to open a path outside the storage root")
        if not p.exists():
            raise FileNotFoundError(str(p))

        folder = p if p.is_dir() else p.parent

        if sys.platform == "win32":
            if select and p.is_file():
                # explorer needs the comma glued to /select and returns exit code 1
                # even on success, so we fire-and-forget.
                subprocess.Popen(["explorer", f"/select,{os.path.normpath(p)}"])
            else:
                os.startfile(str(folder))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            args = ["open", "-R", str(p)] if (select and p.is_file()) else ["open", str(folder)]
            subprocess.Popen(args)
        else:
            subprocess.Popen(["xdg-open", str(folder)])

        return folder


def _escape_csv(value: str) -> str:
    """Neutralise CSV/formula injection (plan section 14)."""
    if value and value[0] in ("=", "+", "-", "@"):
        return "'" + value
    return value


storage = StorageManager()
