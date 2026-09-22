"""In-process event bus for live UI updates.

Watcher and scheduler threads publish to a thread-safe queue.
An async loop drains it and broadcasts to all connected WebSockets.
"""

from __future__ import annotations

import asyncio
import json
import queue
from datetime import datetime
from typing import Any


_event_queue: "queue.Queue[dict]" = queue.Queue()
_connections: set = set()


def publish(event_type: str, data: dict | None = None) -> None:
    """Thread-safe. Call from any thread (watcher, scheduler, request handlers)."""
    _event_queue.put({
        "type": event_type,
        "data": data or {},
        "ts": datetime.now().strftime("%H:%M:%S"),
    })


def connection_count() -> int:
    return len(_connections)


async def handle_connection(websocket) -> None:
    """Accepts a WebSocket and keeps it open until it disconnects."""
    await websocket.accept()
    _connections.add(websocket)
    try:
        # Send a hello so the client knows the channel is live
        await websocket.send_text(json.dumps({
            "type": "hello",
            "data": {"connections": len(_connections)},
            "ts": datetime.now().strftime("%H:%M:%S"),
        }))
        # We don't expect client messages — just keep reading to detect close
        while True:
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        _connections.discard(websocket)


async def broadcast_loop() -> None:
    """Drains the event queue and sends each event to every connected client."""
    while True:
        try:
            event = _event_queue.get_nowait()
        except queue.Empty:
            await asyncio.sleep(0.1)
            continue

        if not _connections:
            continue

        msg = json.dumps(event)
        dead = []
        for ws in list(_connections):
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _connections.discard(ws)