"""Waterfall rows for the dashboard: 10 rows per second, at most 500 columns, one byte per cell."""

from __future__ import annotations

import math

import numpy as np

from core.contracts import FRAME_HEADER

ROWS_PER_S = 10
MAX_COLS = 500
DISPLAY_MAX = 1000.0  # noise-normalised value that maps to full colour


class Display:
    def __init__(self, n_channels: int, fs: float):
        self.n = n_channels
        self.fs = fs
        self.step = math.ceil(n_channels / MAX_COLS)  # channels per column
        self.cols = math.ceil(n_channels / self.step)
        self.samples_per_row = int(fs // ROWS_PER_S)

    def frame(self, x: np.ndarray, t0: float, usable: np.ndarray) -> bytes:
        """x: noise-normalised samples (n, n_channels) starting at stream time t0."""
        spr = self.samples_per_row
        rows = len(x) // spr
        x = np.where(usable, x[: rows * spr], 0.0)
        pad = self.cols * self.step - self.n
        if pad:
            x = np.pad(x, ((0, 0), (0, pad)))
        cells = (x.reshape(rows, spr, self.cols, self.step)
                 .transpose(0, 2, 1, 3).reshape(rows, self.cols, spr * self.step))
        pick = np.abs(cells).argmax(axis=-1)
        v = np.take_along_axis(cells, pick[..., None], axis=-1)[..., 0]
        # Signed log scale: noise (|v| ~ 1) is a faint speckle, an M7 still shows its wave trains.
        d = np.sign(v) * np.log10(1 + np.abs(v)) / np.log10(1 + DISPLAY_MAX)
        cells_u8 = np.clip(np.round(128 + 127 * d), 1, 255).astype(np.uint8)
        return FRAME_HEADER.pack(rows, self.cols, t0) + cells_u8.tobytes()
