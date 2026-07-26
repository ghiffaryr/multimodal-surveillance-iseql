from __future__ import annotations

import asyncio
import json
import time
from typing import AsyncIterator, Dict

async def log_event(stage: str, message: str, **extra) -> Dict:
    payload = {
        "ts": time.time(),
        "stage": stage,
        "message": message,
    }
    payload.update(extra)
    return payload

async def event_stream(queues: asyncio.Queue) -> AsyncIterator[Dict]:
    while True:
        item = await queues.get()
        if item is None:
            break
        yield {"event": "log", "data": json.dumps(item)}
    yield {"event": "end", "data": "{}"}
