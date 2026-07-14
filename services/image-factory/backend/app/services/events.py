"""In-process pub/sub event bus for Server-Sent Events (plan section 11).

The worker runs in a background thread and publishes events; SSE subscribers are
async generators in the API layer. We bridge threads to asyncio using each
subscriber's event loop via call_soon_threadsafe.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field

from app.core.logging import get_logger

logger = get_logger(__name__)

# Known event types: job_progress, worker_status, gpu_status, image_completed, error


@dataclass(eq=False)
class Subscriber:
    """eq=False keeps default identity-based hashing so instances can live in a set."""

    queue: asyncio.Queue
    loop: asyncio.AbstractEventLoop


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[Subscriber] = set()

    def subscribe(self) -> Subscriber:
        loop = asyncio.get_running_loop()
        sub = Subscriber(queue=asyncio.Queue(maxsize=1000), loop=loop)
        self._subscribers.add(sub)
        return sub

    def unsubscribe(self, sub: Subscriber) -> None:
        self._subscribers.discard(sub)

    def publish(self, event_type: str, data: dict) -> None:
        """Thread-safe publish. Callable from the worker thread."""
        payload = json.dumps({"type": event_type, "data": data}, ensure_ascii=False)
        for sub in list(self._subscribers):
            try:
                sub.loop.call_soon_threadsafe(self._safe_put, sub.queue, payload)
            except RuntimeError:
                # Loop is gone; drop the subscriber.
                self._subscribers.discard(sub)

    @staticmethod
    def _safe_put(queue: asyncio.Queue, payload: str) -> None:
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning("SSE subscriber queue full; dropping event")


bus = EventBus()
