"""Background worker: claims queued job_items, generates images, and records
results. Runs in a daemon thread started by the FastAPI lifespan.

Key behaviours (plan sections 7 & 16):
- Atomic claim of the oldest queued item with a lock + timeout.
- Heartbeat row so a watchdog/restart can reclaim stale items.
- On startup, requeue stale `running` items whose lock expired.
- Skip generating if the item already produced a completed image (dedupe).
- Bounded retries; disk guard before each item.
"""

from __future__ import annotations

import json
import random
import threading
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.comfyui.client import make_generator
from app.comfyui.generator import GenerationRequest
from app.core.config import settings
from app.core.logging import get_logger
from app.core.utils import job_folder_name, new_id, parse_iso, utcnow_iso
from app.db.base import SessionLocal
from app.models import Image, Job, JobItem, WorkerHeartbeat
from app.services import job_service, layout_renderer, quality_gate
from app.services.events import bus
from app.storage.manager import storage

logger = get_logger(__name__)


class Worker:
    def __init__(self) -> None:
        self.worker_id = settings.worker_id
        self.gpu_id = settings.gpu_id
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._generator = None
        self._current_job_id: str | None = None

    # --- lifecycle ----------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="worker", daemon=True)
        self._thread.start()
        logger.info("Worker %s started", self.worker_id)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Worker %s stopped", self.worker_id)

    # --- main loop ----------------------------------------------------
    def _run(self) -> None:
        self._generator = make_generator()
        with SessionLocal() as db:
            self._recover_stale_items(db)
        self._heartbeat("idle", None)

        while not self._stop.is_set():
            try:
                with SessionLocal() as db:
                    item = self._claim_next(db)
                    if item is None:
                        self._heartbeat("idle", None)
                        self._stop.wait(settings.poll_interval_seconds)
                        continue
                    self._current_job_id = item.job_id
                    try:
                        self._process_item(db, item)
                    finally:
                        self._current_job_id = None
            except Exception:  # noqa: BLE001 - keep the loop alive
                logger.exception("Worker loop error")
                self._stop.wait(settings.poll_interval_seconds)

        self._heartbeat("stopped", None)

    def interrupt_job(self, job_id: str) -> None:
        if self._current_job_id != job_id or self._generator is None:
            return
        interrupt = getattr(self._generator, "interrupt", None)
        if interrupt is not None:
            interrupt()

    # --- claiming -----------------------------------------------------
    def _claim_next(self, db: Session) -> JobItem | None:
        """Atomically claim the oldest queued item from a non-paused job."""
        now = utcnow_iso()
        locked_until = (parse_iso(now) + timedelta(seconds=settings.lock_timeout_seconds)).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )

        # Find candidate whose parent job is queued/running (not paused/cancelled).
        candidate = db.execute(
            select(JobItem.id)
            .join(Job, Job.id == JobItem.job_id)
            .where(
                JobItem.status == "queued",
                Job.status.in_(("queued", "running")),
            )
            .order_by(JobItem.created_at, JobItem.item_index)
            .limit(1)
        ).scalar_one_or_none()

        if candidate is None:
            return None

        # Conditional update acts as the lock: only succeeds if still queued.
        result = db.execute(
            update(JobItem)
            .where(JobItem.id == candidate, JobItem.status == "queued")
            .values(
                status="running",
                locked_by=self.worker_id,
                locked_until=locked_until,
                attempts=JobItem.attempts + 1,
                updated_at=now,
            )
        )
        if result.rowcount == 0:
            db.rollback()
            return None
        db.commit()

        item = db.get(JobItem, candidate)
        # Mark the parent job running.
        job = db.get(Job, item.job_id)
        if job and job.status == "queued":
            job.status = "running"
            job.updated_at = now
            db.commit()
        return item

    # --- processing ---------------------------------------------------
    def _process_item(self, db: Session, item: JobItem) -> None:
        job = db.get(Job, item.job_id)
        if job is None or job.status in ("cancelled", "paused"):
            self._release_item(db, item, "queued" if job and job.status == "paused" else "cancelled")
            return

        # Dedupe: if an image already exists for this item, don't regenerate.
        existing = db.scalar(select(Image).where(Image.job_item_id == item.id))
        if existing is not None:
            item.status = "completed"
            item.updated_at = utcnow_iso()
            db.commit()
            job_service.recompute_job_progress(db, item.job_id)
            return

        # Disk guard.
        if storage.disk_free_bytes() < settings.min_free_disk_bytes:
            self._fail_item(db, item, "Insufficient disk space (disk guard)")
            bus.publish("error", {"source": "worker", "message": "Disk guard tripped"})
            return

        self._heartbeat("running", item.id)
        params = json.loads(item.params_json) if item.params_json else {}
        req = GenerationRequest(
            prompt=item.prompt,
            negative_prompt=item.negative_prompt or "",
            seed=item.seed or 0,
            width=item.width,
            height=item.height,
            steps=int(params.get("steps") or settings.default_steps),
            cfg=float(params.get("cfg") or settings.default_cfg),
            sampler=params.get("sampler") or settings.default_sampler,
            scheduler=params.get("scheduler") or settings.default_scheduler,
            model=params.get("model") or settings.default_model,
            params=params,
        )

        try:
            result = self._generator.generate(req)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Generation failed for item %s", item.id)
            if item.attempts <= settings.max_retries:
                self._release_item(db, item, "queued", error=str(exc))
            else:
                self._fail_item(db, item, f"Max retries exceeded: {exc}")
            return

        assessment = quality_gate.assess_image(result.image_bytes)
        if result.backend != "mock" and not assessment.accepted:
            self._reject_low_quality(db, item, params, assessment)
            return

        layout_metadata = None
        creative = params.get("creative") or {}
        if creative.get("apply_layout") and creative.get("title_text"):
            logo_path = storage.logo_asset_path(
                user_id=job.user_id,
                asset_id=creative.get("logo_asset_id"),
            )
            try:
                laid_out = layout_renderer.render_layout(
                    result.image_bytes,
                    title=creative["title_text"],
                    title_position=creative.get("title_position") or "left",
                    logo_path=logo_path,
                )
                result.image_bytes = laid_out.image_bytes
                layout_metadata = laid_out.metadata()
            except (OSError, ValueError) as exc:
                self._fail_item(db, item, f"Layout rendering failed: {exc}")
                return

        # Re-check cancellation after a possibly long generation.
        db.refresh(job)
        if job.status == "cancelled":
            logger.info("Job %s cancelled during generation; discarding result", job.id)
            return

        self._save_result(
            db,
            job,
            item,
            req,
            result,
            quality=assessment.to_dict(),
            layout=layout_metadata,
        )

    def _save_result(
        self,
        db: Session,
        job: Job,
        item: JobItem,
        req: GenerationRequest,
        result,
        *,
        quality: dict | None = None,
        layout: dict | None = None,
    ) -> None:
        folder = job_folder_name(job.created_at, job.id.split("_")[-1])
        model_tag = (req.model or "model").replace(" ", "-")
        filename = (
            f"job_{job.id.split('_')[-1][:6]}_img_{item.item_index:04d}"
            f"_seed_{result.seed}_model_{model_tag}.png"
        )
        saved = storage.save_image_bytes(
            user_id=job.user_id, job_folder=folder, filename=filename, data=result.image_bytes
        )

        metadata = {
            "prompt": item.prompt,
            "negative_prompt": item.negative_prompt,
            "seed": result.seed,
            "model": req.model,
            "width": saved.width,
            "height": saved.height,
            "steps": req.steps,
            "cfg": req.cfg,
            "sampler": req.sampler,
            "scheduler": req.scheduler,
            "backend": result.backend,
            "duration_seconds": round(result.duration_seconds, 3),
            "generated_at": utcnow_iso(),
            "quality": quality,
            "layout": layout,
            "creative": req.params.get("creative"),
            "visual_brief": (req.params.get("creative_package") or {}).get("brief"),
            "prompt_source": (req.params.get("creative_package") or {}).get("source"),
            "is_placeholder": result.backend == "mock",
        }

        image = Image(
            id=new_id("img"),
            job_id=job.id,
            job_item_id=item.id,
            user_id=job.user_id,
            file_path=str(saved.file_path),
            thumbnail_path=str(saved.thumbnail_path),
            seed=result.seed,
            width=saved.width,
            height=saved.height,
            file_size=saved.file_size,
            status="completed",
            metadata_json=json.dumps(metadata, ensure_ascii=False),
            created_at=utcnow_iso(),
        )
        db.add(image)
        item.status = "completed"
        item.locked_by = None
        item.locked_until = None
        item.error_message = None
        item.updated_at = utcnow_iso()
        db.commit()

        storage.write_metadata(
            user_id=job.user_id,
            job_folder=folder,
            metadata={"job_id": job.id, "last_image": metadata},
        )
        storage.append_result_row(
            user_id=job.user_id,
            job_folder=folder,
            row={
                "item_index": item.item_index,
                "source_row_id": item.source_row_id or "",
                "prompt": item.prompt,
                "seed": result.seed,
                "status": "completed",
                "file": storage.relative(saved.file_path),
            },
            fieldnames=["item_index", "source_row_id", "prompt", "seed", "status", "file"],
        )

        job_service.recompute_job_progress(db, job.id)
        bus.publish(
            "image_completed",
            {
                "image_id": image.id,
                "job_id": job.id,
                "job_item_id": item.id,
                "thumbnail": storage.relative(saved.thumbnail_path),
            },
        )
        logger.info("Item %s completed in %.2fs", item.id, result.duration_seconds)

    def _reject_low_quality(self, db: Session, item: JobItem, params: dict, assessment) -> None:
        history = list(params.get("quality_rejections") or [])
        history.append(
            {
                "seed": item.seed,
                "attempt": item.attempts,
                **assessment.to_dict(),
            }
        )
        params["quality_rejections"] = history
        item.params_json = json.dumps(params, ensure_ascii=False)
        if item.attempts <= settings.max_retries:
            previous_seed = item.seed
            item.seed = random.randint(1, 2**31 - 1)
            logger.warning(
                "Quality gate rejected item %s seed %s (%s); retrying with seed %s",
                item.id,
                previous_seed,
                assessment.reason,
                item.seed,
            )
            self._release_item(db, item, "queued", error=f"Quality retry: {assessment.reason}")
        else:
            self._fail_item(db, item, f"Quality gate rejected image: {assessment.reason}")

    # --- item state helpers ------------------------------------------
    def _release_item(self, db: Session, item: JobItem, status: str, error: str | None = None) -> None:
        item.status = status
        item.locked_by = None
        item.locked_until = None
        if error:
            item.error_message = error
        item.updated_at = utcnow_iso()
        db.commit()
        job_service.recompute_job_progress(db, item.job_id)

    def _fail_item(self, db: Session, item: JobItem, message: str) -> None:
        item.status = "failed"
        item.locked_by = None
        item.locked_until = None
        item.error_message = message
        item.updated_at = utcnow_iso()
        db.commit()
        job_service.recompute_job_progress(db, item.job_id)
        bus.publish("error", {"source": "worker", "job_item_id": item.id, "message": message})

    # --- recovery / heartbeat ----------------------------------------
    def _recover_stale_items(self, db: Session) -> None:
        """Requeue items left `running` by a previous crashed worker."""
        now = parse_iso(utcnow_iso())
        stale = db.scalars(select(JobItem).where(JobItem.status == "running")).all()
        recovered = 0
        for item in stale:
            has_image = db.scalar(select(Image).where(Image.job_item_id == item.id))
            if has_image is not None:
                item.status = "completed"
            else:
                lock_expiry = parse_iso(item.locked_until)
                if lock_expiry is None or lock_expiry < now:
                    item.status = "queued"
                    item.locked_by = None
                    item.locked_until = None
                    recovered += 1
            item.updated_at = utcnow_iso()
        if stale:
            db.commit()
        if recovered:
            logger.info("Recovered %d stale running item(s) back to queued", recovered)

    def _heartbeat(self, status: str, current_item: str | None) -> None:
        try:
            with SessionLocal() as db:
                hb = db.get(WorkerHeartbeat, self.worker_id)
                now = utcnow_iso()
                if hb is None:
                    hb = WorkerHeartbeat(
                        worker_id=self.worker_id,
                        gpu_id=self.gpu_id,
                        status=status,
                        current_job_item_id=current_item,
                        last_seen_at=now,
                    )
                    db.add(hb)
                else:
                    hb.status = status
                    hb.current_job_item_id = current_item
                    hb.last_seen_at = now
                db.commit()
            bus.publish("worker_status", {"worker_id": self.worker_id, "status": status})
        except Exception:  # noqa: BLE001
            logger.exception("Heartbeat failed")


worker = Worker()
