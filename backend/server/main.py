"""FastAPI app: REST controls, one WebSocket that pushes everything, and the static files.

    uvicorn server.main:app --port 8000      (run from backend/)
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core import config
from core.contracts import RecordingMeta
from core.recording import open_recording
from server.session import SPEEDS, Hub, Session

app = FastAPI(title="SeaNerve")
hub = Hub()
state: dict[str, Session | None] = {"session": None}


class StartSession(BaseModel):
    source_id: str
    speed: float = 1.0


class SetSpeed(BaseModel):
    speed: float


def _check_speed(speed: float) -> float:
    if speed not in SPEEDS:
        raise HTTPException(400, f"speed must be one of {SPEEDS}")
    return speed


def _session() -> Session:
    if state["session"] is None:
        raise HTTPException(409, "no session running")
    return state["session"]


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/sources")
def sources() -> list[dict]:
    out = []
    root = config.RECORDINGS_DIR
    for meta_path in sorted(root.glob("*/meta.json")) if root.exists() else []:
        source_id = meta_path.parent.name  # the folder name is what POST /api/session takes
        if source_id.startswith("random-"):  # training and evaluation data, not for the demo
            continue
        m = RecordingMeta.model_validate_json(meta_path.read_text())
        out.append({"id": source_id, "title": m.title, "kind": m.kind, "duration_s": m.duration_s})
    return out


@app.post("/api/session")
async def start_session(body: StartSession) -> dict:
    _check_speed(body.speed)
    path = config.RECORDINGS_DIR / body.source_id
    if not (path / "meta.json").exists():
        raise HTTPException(404, f"no recording {body.source_id!r}")
    if state["session"] is not None:
        await state["session"].stop()
    session = Session(open_recording(path), body.speed, hub)
    state["session"] = session
    session.start()
    return session.hello.to_json()


@app.post("/api/session/pause")
async def pause() -> dict:
    session = _session()
    session.paused = True
    await hub.send_model(session.status())  # dashboards learn at once, not at the next block
    return {"paused": True}


@app.post("/api/session/resume")
async def resume() -> dict:
    session = _session()
    session.paused = False
    await hub.send_model(session.status())
    return {"paused": False}


@app.post("/api/session/speed")
async def set_speed(body: SetSpeed) -> dict:
    session = _session()
    session.speed = _check_speed(body.speed)
    await hub.send_model(session.status())
    return {"speed": body.speed}


@app.delete("/api/session")
async def stop_session() -> dict:
    if state["session"] is not None:
        await state["session"].stop()
        state["session"] = None
    return {"stopped": True}


@app.get("/api/events")
def events() -> list[dict]:
    session = state["session"]
    return [a.to_json() for a in session.alerts] if session else []


@app.websocket("/ws")
async def websocket(ws: WebSocket) -> None:
    await ws.accept()
    hub.clients.add(ws)
    try:
        if state["session"] is not None:
            await state["session"].greet(ws)
        while True:
            await ws.receive_text()  # the dashboard never sends; this just waits for close
    except WebSocketDisconnect:
        pass
    finally:
        hub.clients.discard(ws)


app.mount("/geo", StaticFiles(directory=config.GEO_DIR), name="geo")
_dist = config.REPO_DIR / "frontend" / "dist"
if _dist.exists():  # the built dashboard: one process, one port for the demo
    app.mount("/", StaticFiles(directory=_dist, html=True), name="dashboard")
