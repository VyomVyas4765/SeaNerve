"""STA/LTA trigger: per channel, short-term over long-term average energy.

Both averages are recursive (one multiply-add per sample), so the cost per block stays flat.
"""

from __future__ import annotations

import numpy as np

from core import config


class StaLta:
    def __init__(self, n_channels: int, fs: float = config.FS_HZ):
        self.fs = fs
        self.a_sta = 1.0 / (config.STA_S * fs)
        self.a_lta = 1.0 / (config.LTA_S * fs)
        self.sta: np.ndarray | None = None
        self.lta: np.ndarray | None = None
        self.triggered = np.zeros(n_channels, dtype=bool)
        self.onset = np.full(n_channels, np.nan)  # time of each channel's latest trigger-on
        self.ratio = np.zeros(n_channels)

    def process(self, x: np.ndarray, t0: float) -> np.ndarray:
        """Feed a block that starts at stream time t0. Returns channels that triggered in it."""
        cf = np.asarray(x, dtype=np.float64) ** 2
        if self.sta is None:
            self.sta = cf.mean(axis=0)
            self.lta = self.sta.copy()
        sta, lta, trig = self.sta, self.lta, self.triggered
        new = np.zeros_like(trig)
        for i, c in enumerate(cf):
            sta += self.a_sta * (c - sta)
            free = ~trig
            lta[free] += self.a_lta * (c[free] - lta[free])  # frozen while triggered
            t = t0 + i / self.fs
            if t < config.WARMUP_S:
                continue
            ratio = sta / (lta + 1e-30)
            on = free & (ratio > config.TRIGGER_ON)
            if on.any():
                trig[on] = True
                new[on] = True
                self.onset[on] = t - config.ONSET_DELAY_S
            off = trig & ~on & (ratio < config.TRIGGER_OFF)
            trig[off] = False
        self.ratio = sta / (lta + 1e-30)
        return np.flatnonzero(new)
