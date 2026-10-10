"""Recording: one folder with data.npy (float32, time x channels) and meta.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from core.contracts import RecordingMeta


@dataclass
class Recording:
    path: Path
    meta: RecordingMeta
    data: np.ndarray  # memory-mapped, shape (n_samples, n_channels)


def open_recording(path: str | Path) -> Recording:
    path = Path(path)
    meta = RecordingMeta.model_validate_json((path / "meta.json").read_text())
    data = np.load(path / "data.npy", mmap_mode="r")
    if data.shape != (meta.n_samples, meta.n_channels):
        raise ValueError(f"{path}: data shape {data.shape} does not match meta")
    return Recording(path, meta, data)


def write_meta(path: str | Path, meta: RecordingMeta) -> None:
    Path(path, "meta.json").write_text(json.dumps(meta.to_json(), indent=2))


def write_recording(path: str | Path, data: np.ndarray, meta: RecordingMeta) -> Recording:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    np.save(path / "data.npy", np.ascontiguousarray(data, dtype=np.float32))
    write_meta(path, meta)
    return open_recording(path)
