"""Save a waterfall PNG of a recording to data/plots/<id>.png, to check it by eye.

    python tools/plot_recording.py car_nicobar_m7 vessel_crossing
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from scipy.signal import butter, sosfiltfilt  # noqa: E402

from core.config import PLOTS_DIR, RECORDINGS_DIR  # noqa: E402
from core.geo import channel_km  # noqa: E402
from core.recording import open_recording  # noqa: E402
from core.synth import scenarios  # noqa: E402
from core.synth.generator import make_context  # noqa: E402

MAX_COLS = 500
ROWS_PER_S = 10


def waterfall(data: np.ndarray, fs: float) -> np.ndarray:
    """1-45 Hz, per-channel noise-normalised, max-|value| per display cell, clipped at +-4."""
    sos = butter(4, [1.0, 45.0], btype="band", fs=fs, output="sos")
    step = max(1, data.shape[1] // MAX_COLS)
    x = sosfiltfilt(sos, np.asarray(data[:, ::step], dtype=np.float64), axis=0)
    x /= np.median(np.abs(x), axis=0) + 1e-9
    rows = int(fs // ROWS_PER_S)
    n = (x.shape[0] // rows) * rows
    cells = x[:n].reshape(-1, rows, x.shape[1])
    idx = np.abs(cells).argmax(axis=1)
    picked = np.take_along_axis(cells, idx[:, None, :], axis=1)[:, 0, :]
    return np.clip(picked, -4, 4)


def plot(recording_id: str) -> Path:
    rec = open_recording(RECORDINGS_DIR / recording_id)
    m = rec.meta
    img = waterfall(rec.data, m.fs_hz)
    km = channel_km(m)
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.imshow(img, cmap="seismic", vmin=-4, vmax=4, aspect="auto", interpolation="nearest",
              extent=[km[0], km[-1], m.duration_s, 0])
    for ev in m.truth:
        if ev.cls == "earthquake" and m.kind == "synthetic":
            quake = next(e for e in scenarios.get(m.id).events if hasattr(e, "magnitude"))
            tp, ts = quake.arrivals(make_context(scenarios.get(m.id)))
            ax.plot(km, tp, "--", color="lime", lw=0.8, label="true P")
            ax.plot(km, ts, ":", color="yellow", lw=0.8, label="true S")
            ax.legend(loc="lower right")
    ax.set_xlabel("distance along cable (km)")
    ax.set_ylabel("time (s)")
    ax.set_title(f"{m.id}: {m.title}")
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)
    out = PLOTS_DIR / f"{recording_id}.png"
    fig.savefig(out, dpi=90, bbox_inches="tight")
    plt.close(fig)
    return out


if __name__ == "__main__":
    for rid in sys.argv[1:] or [p.name for p in sorted(RECORDINGS_DIR.iterdir())]:
        print(plot(rid))
