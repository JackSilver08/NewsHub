"""Hardware detection (plan section 15).

Never crashes when there is no NVIDIA GPU; returns a best-effort snapshot and a
recommendation for a suitable model given the detected VRAM.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass, field

import psutil

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class GpuInfo:
    name: str
    vram_total_mb: int | None = None
    vram_used_mb: int | None = None
    utilization_pct: int | None = None
    temperature_c: int | None = None
    driver: str | None = None


@dataclass
class HardwareInfo:
    os: str
    cpu: str
    cpu_cores: int
    ram_total_gb: float
    ram_available_gb: float
    disk_total_gb: float
    disk_free_gb: float
    gpus: list[GpuInfo] = field(default_factory=list)
    cuda_available: bool = False
    has_nvidia_gpu: bool = False
    recommended_model: str = "sd15"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        return data


def _query_nvidia_smi() -> list[GpuInfo]:
    """Query nvidia-smi if present. Returns [] when unavailable."""
    if shutil.which("nvidia-smi") is None:
        return []
    query = "name,memory.total,memory.used,utilization.gpu,temperature.gpu,driver_version"
    try:
        out = subprocess.run(
            [
                "nvidia-smi",
                f"--query-gpu={query}",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("nvidia-smi query failed: %s", exc)
        return []

    gpus: list[GpuInfo] = []
    for line in out.stdout.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6:
            continue

        def _int(value: str) -> int | None:
            try:
                return int(float(value))
            except ValueError:
                return None

        gpus.append(
            GpuInfo(
                name=parts[0],
                vram_total_mb=_int(parts[1]),
                vram_used_mb=_int(parts[2]),
                utilization_pct=_int(parts[3]),
                temperature_c=_int(parts[4]),
                driver=parts[5],
            )
        )
    return gpus


def _recommend_model(vram_mb: int | None) -> str:
    """Map available VRAM to a recommended model (plan section 4)."""
    if vram_mb is None:
        return "sd15"
    gb = vram_mb / 1024
    if gb >= 24:
        return "flux-schnell"
    if gb >= 16:
        return "sdxl"
    if gb >= 12:
        return "sdxl"
    if gb >= 8:
        return "sdxl-lowvram"
    if gb >= 4:
        return "sd15"
    return "sd15-cpu"


def detect_hardware() -> HardwareInfo:
    vm = psutil.virtual_memory()
    disk = shutil.disk_usage(str(settings.storage_root.anchor or "/"))

    gpus = _query_nvidia_smi()
    has_nvidia = len(gpus) > 0

    cuda_available = False
    try:
        import torch  # type: ignore

        cuda_available = bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001 - torch is optional
        cuda_available = False

    max_vram = max((g.vram_total_mb or 0 for g in gpus), default=0)
    recommended = _recommend_model(max_vram if has_nvidia else None)

    warnings: list[str] = []
    if not has_nvidia:
        warnings.append(
            "No NVIDIA GPU detected. CPU fallback is extremely slow; "
            "large batches are disabled by default and a small model is recommended."
        )
    if disk.free < settings.min_free_disk_bytes:
        warnings.append("Low free disk space; a large batch may fail.")

    info = HardwareInfo(
        os=f"{platform.system()} {platform.release()}",
        cpu=platform.processor() or platform.machine(),
        cpu_cores=psutil.cpu_count(logical=True) or 0,
        ram_total_gb=round(vm.total / 1024**3, 1),
        ram_available_gb=round(vm.available / 1024**3, 1),
        disk_total_gb=round(disk.total / 1024**3, 1),
        disk_free_gb=round(disk.free / 1024**3, 1),
        gpus=gpus,
        cuda_available=cuda_available,
        has_nvidia_gpu=has_nvidia,
        recommended_model=recommended,
        warnings=warnings,
    )
    return info
