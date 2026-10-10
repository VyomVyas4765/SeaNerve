"""A rolling window of the last N seconds of a (time x channels) signal."""

from __future__ import annotations

import numpy as np


class RingBuffer:
    def __init__(self, seconds: float, n_channels: int, fs: float):
        self.fs = fs
        self.cap = int(seconds * fs)
        self.data = np.zeros((self.cap, n_channels), dtype=np.float32)
        self.n_written = 0

    @property
    def t_start(self) -> float:
        return max(0, self.n_written - self.cap) / self.fs

    @property
    def t_end(self) -> float:
        return self.n_written / self.fs

    def push(self, block: np.ndarray) -> None:
        idx = np.arange(self.n_written, self.n_written + len(block)) % self.cap
        self.data[idx] = block
        self.n_written += len(block)

    def get(self, t0: float, n: int, channel: int) -> np.ndarray | None:
        """n samples of one channel starting at stream time t0, or None if not all held."""
        i0 = int(round(t0 * self.fs))
        if i0 < self.n_written - self.cap or i0 + n > self.n_written or n <= 0:
            return None
        return self.data[np.arange(i0, i0 + n) % self.cap, channel]
