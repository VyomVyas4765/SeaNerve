"""Replay loop: plays a Recording through the engine at 1, 2 or 5x and pushes what comes out.

Every 100 ms of wall time the stream clock moves on by 100 ms x speed. Each full second of data
goes to StreamEngine.feed in a worker thread, so filtering never blocks the socket. After the data
runs out the clock keeps going, so the city countdowns finish.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid

import numpy as np
from fastapi import WebSocket

from core.contracts import Alert, Status
from core.pipeline.engine import StreamEngine
from core.recording import Recording

log = logging.getLogger("seanerve")

TICK_S = 0.1
BLOCK_S = 1.0
SPEEDS = (1.0, 2.0, 5.0)


class Hub:
    """Every connected dashboard. Messages go to all of them."""

    def __init__(self):
        self.clients: set[WebSocket] = set()

    async def send(self, payload: str | bytes) -> None:
        for ws in list(self.clients):
            try:
                if isinstance(payload, bytes):
                    await ws.send_bytes(payload)
                else:
                    await ws.send_text(payload)
            except Exception:  # a closed tab; forget it
                self.clients.discard(ws)

    async def send_model(self, model) -> None:
        await self.send(json.dumps(model.to_json()))


class Session:
    def __init__(self, rec: Recording, speed: float, hub: Hub):
        self.rec = rec
        self.hub = hub
        self.speed = speed
        self.paused = False
        self.engine = StreamEngine(rec.meta, rec.meta.id)
        self.hello = self.engine.hello(session_id=uuid.uuid4().hex[:12])
        self.clock = 0.0  # stream time
        self.next_sample = 0
        self.last_status_s = 0.0
        self.latency_ms: float | None = None
        self.stage_ms: dict[str, float] = {}
        self.kept = 0.0
        self.task: asyncio.Task | None = None

    @property
    def ended(self) -> bool:
        return self.next_sample >= self.rec.meta.n_samples

    @property
    def alerts(self) -> list[Alert]:
        return list(self.engine.alerts.values())

    def start(self) -> None:
        self.task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    def status(self) -> Status:
        return Status(t_s=round(self.clock, 3), speed=self.speed, paused=self.paused,
                      latency_ms=self.latency_ms, stage_ms=self.stage_ms,
                      data_kept_ratio=round(self.kept, 4), ended=self.ended)

    async def greet(self, ws: WebSocket) -> None:
        """Bring a newly connected dashboard up to date."""
        await ws.send_text(json.dumps(self.hello.to_json()))
        for alert in self.alerts:
            await ws.send_text(json.dumps(alert.to_json()))
        await ws.send_text(json.dumps(self.status().to_json()))

    async def _run(self) -> None:
        await self.hub.send_model(self.hello)
        loop = asyncio.get_running_loop()
        last = loop.time()
        block = int(BLOCK_S * self.rec.meta.fs_hz)
        try:
            while True:
                await asyncio.sleep(TICK_S)
                now = loop.time()
                if not self.paused:
                    self.clock += (now - last) * self.speed
                last = now
                while not self.ended and (self.next_sample + block) / self.rec.meta.fs_hz <= self.clock:
                    await self._feed(block)
                if self.ended and self.clock - self.last_status_s >= 1.0:
                    self.last_status_s = self.clock
                    await self.hub.send_model(self.status())
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("replay loop crashed")

    async def _feed(self, block: int) -> None:
        i0 = self.next_sample
        data = np.asarray(self.rec.data[i0:i0 + block])
        self.next_sample = i0 + len(data)
        out = await asyncio.to_thread(self.engine.feed, data)
        self.latency_ms = round(sum(out.stage_ms.values()), 1)
        self.stage_ms = out.stage_ms
        self.kept = out.data_kept_ratio
        await self.hub.send(out.frame)
        for msg in out.messages:
            await self.hub.send_model(msg)
        self.last_status_s = out.t_end
        await self.hub.send_model(self.status())
