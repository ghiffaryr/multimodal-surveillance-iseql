from __future__ import annotations

import asyncio
import json
import time
from typing import AsyncIterator


def format_sse_event(event: str, data: str) -> str:
    lines = ["event: " + event]
    for chunk_line in data.split("\n"):
        lines.append("data: " + chunk_line)
    lines.append("")
    return "\n".join(lines) + "\n"


def make_log_entry(stage: str, message: str, **extra) -> dict:
    return {"ts": time.time(), "stage": stage, "message": message, **extra}


async def drain_queue_into_sse(queue: asyncio.Queue) -> AsyncIterator[str]:
    while True:
        item = await queue.get()
        yield format_sse_event("log", json.dumps(item))
        if item.get("message") == "<<RUN_DONE>>":
            yield format_sse_event("end", "{}")
            return
        if item.get("message") == "<<RUN_FAILED>>":
            yield format_sse_event("end", "{}")
            return
