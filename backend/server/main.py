"""FastAPI app. Routes and the WebSocket are added at hour 9; for now it only proves the server runs."""

from fastapi import FastAPI

app = FastAPI(title="SeaNerve")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
