import json

from fastapi.testclient import TestClient

from core import config
from core.contracts import FRAME_HEADER
from core.synth import scenarios
from core.synth.generator import build_recording
from server import main


def test_session_streams_hello_frames_and_status(tmp_path, monkeypatch):
    sc = scenarios.random_scenario(3, n_channels=50, duration_s=12.0)
    build_recording(sc, tmp_path / "tiny")
    monkeypatch.setattr(config, "RECORDINGS_DIR", tmp_path)

    with TestClient(main.app) as client:
        assert [s["id"] for s in client.get("/api/sources").json()] == ["tiny"]
        assert client.post("/api/session", json={"source_id": "nope"}).status_code == 404
        assert client.post("/api/session", json={"source_id": "tiny", "speed": 3}).status_code == 400
        hello = client.post("/api/session", json={"source_id": "tiny", "speed": 5}).json()
        assert hello["type"] == "hello" and hello["cols"] == 50 and hello["session_id"]

        with client.websocket_connect("/ws") as ws:
            first = json.loads(ws.receive_text())
            assert first["type"] == "hello"
            seen = set()
            for _ in range(12):
                msg = ws.receive()
                if msg.get("bytes"):
                    rows, cols, _ = FRAME_HEADER.unpack_from(msg["bytes"])
                    assert (rows, cols) == (10, 50)
                    seen.add("frame")
                else:
                    seen.add(json.loads(msg["text"])["type"])
                if {"frame", "status"} <= seen:
                    break
            assert {"frame", "status"} <= seen

        assert client.post("/api/session/pause").json() == {"paused": True}
        assert client.delete("/api/session").json() == {"stopped": True}
