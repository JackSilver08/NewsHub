"""Server-Sent Events endpoint for realtime progress (plan section 11)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.services.events import bus

router = APIRouter(prefix="/api", tags=["events"])


@router.get("/events")
async def events(request: Request):
    sub = bus.subscribe()

    async def event_stream():
        try:
            # Initial comment to open the stream promptly.
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(sub.queue.get(), timeout=15.0)
                    yield f"data: {payload}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat comment keeps proxies from closing the connection.
                    yield ": ping\n\n"
        finally:
            bus.unsubscribe(sub)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
