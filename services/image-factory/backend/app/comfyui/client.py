"""ComfyUI HTTP client.

Submits an API-format workflow, polls its prompt history, and fetches the produced
image bytes. History polling is deliberate: CPU generation can emit no WebSocket
messages for minutes, which must not be mistaken for a failed request.

This is written for the real ComfyUI API but is only exercised when
COMFYUI_ENABLED=true. For development, MockGenerator is used instead.
"""

from __future__ import annotations

import time
import uuid

import httpx

from app.comfyui.generator import GenerationRequest, GenerationResult
from app.comfyui.workflow_builder import WorkflowBuilder
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ComfyUIError(RuntimeError):
    pass


class ComfyUIClient:
    backend_name = "comfyui"

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.comfyui_base_url).rstrip("/")
        self.client_id = uuid.uuid4().hex
        self.builder = WorkflowBuilder()
        self._http = httpx.Client(base_url=self.base_url, timeout=30.0)

    def health_check(self) -> bool:
        try:
            resp = self._http.get("/system_stats", timeout=5.0)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    def _queue_prompt(self, graph: dict) -> str:
        payload = {"prompt": graph, "client_id": self.client_id}
        resp = self._http.post("/prompt", json=payload)
        if resp.status_code != 200:
            raise ComfyUIError(f"Queue prompt failed: {resp.status_code} {resp.text}")
        return resp.json()["prompt_id"]

    def _fetch_image(self, filename: str, subfolder: str, folder_type: str) -> bytes:
        resp = self._http.get(
            "/view",
            params={"filename": filename, "subfolder": subfolder, "type": folder_type},
        )
        resp.raise_for_status()
        return resp.content

    def generate(self, req: GenerationRequest) -> GenerationResult:
        start = time.monotonic()
        graph = self.builder.build(req)
        prompt_id = self._queue_prompt(graph)
        deadline = start + settings.comfyui_timeout_seconds
        image_bytes = self._wait_for_image(prompt_id, deadline)
        return GenerationResult(
            image_bytes=image_bytes,
            width=req.width,
            height=req.height,
            seed=req.seed,
            backend=self.backend_name,
            duration_seconds=time.monotonic() - start,
        )

    def _get_history(self, prompt_id: str) -> dict:
        resp = self._http.get(f"/history/{prompt_id}", timeout=15.0)
        resp.raise_for_status()
        return resp.json().get(prompt_id, {})

    def _image_from_history(self, history: dict) -> bytes | None:
        outputs = history.get("outputs", {})
        for node_output in outputs.values():
            for image in node_output.get("images", []):
                return self._fetch_image(
                    image["filename"], image.get("subfolder", ""), image.get("type", "output")
                )
        return None

    @staticmethod
    def _history_error(history: dict) -> str | None:
        status = history.get("status") or {}
        messages = status.get("messages") or []
        for message in messages:
            if not isinstance(message, (list, tuple)) or not message:
                continue
            event = message[0]
            if event not in ("execution_error", "execution_interrupted"):
                continue
            detail = message[1] if len(message) > 1 and isinstance(message[1], dict) else {}
            return str(
                detail.get("exception_message")
                or detail.get("node_type")
                or event.replace("_", " ")
            )
        if status.get("completed") is False and status.get("status_str") == "error":
            return "ComfyUI execution failed"
        return None

    def _wait_for_image(self, prompt_id: str, deadline: float) -> bytes:
        last_connection_error: str | None = None
        while time.monotonic() < deadline:
            try:
                history = self._get_history(prompt_id)
                error = self._history_error(history)
                if error:
                    raise ComfyUIError(f"Prompt {prompt_id} failed: {error}")
                image = self._image_from_history(history)
                if image is not None:
                    return image
                last_connection_error = None
            except httpx.HTTPError as exc:
                # A short HTTP outage must not submit a duplicate prompt. Keep
                # polling the same prompt id until the overall deadline.
                last_connection_error = str(exc)

            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(2.0, remaining))

        suffix = f"; last connection error: {last_connection_error}" if last_connection_error else ""
        raise ComfyUIError(
            f"Timeout after {settings.comfyui_timeout_seconds}s waiting for prompt {prompt_id}{suffix}"
        )

    def _collect_output(self, prompt_id: str) -> bytes:
        """Fetch a completed prompt output; retained for diagnostics/tests."""
        history = self._get_history(prompt_id)
        error = self._history_error(history)
        if error:
            raise ComfyUIError(f"Prompt {prompt_id} failed: {error}")
        image = self._image_from_history(history)
        if image is None:
            raise ComfyUIError(f"No image in outputs for prompt {prompt_id}")
        return image

    def interrupt(self) -> None:
        try:
            self._http.post("/interrupt", timeout=5.0)
        except httpx.HTTPError as exc:  # noqa: BLE001
            logger.warning("Interrupt failed: %s", exc)

    def close(self) -> None:
        self._http.close()


def make_generator():
    """Return the active generation backend based on settings."""
    if settings.comfyui_enabled:
        logger.info("Using ComfyUI backend at %s", settings.comfyui_base_url)
        return ComfyUIClient()
    from app.comfyui.mock_generator import MockGenerator

    logger.info("Using MOCK generation backend (COMFYUI_ENABLED=false)")
    return MockGenerator()
