"""Cleaning, one block at a time.

Remove the noise shared by the whole cable, split into frequency bands with causal filters whose
state carries over between blocks, and divide each channel by its running noise level.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, sosfilt

from core import config

BANDS = {
    "quake": config.QUAKE_BAND_HZ,  # earthquakes: trigger, gate, picks
    "local": config.LOCAL_BAND_HZ,  # ships and anchors: the tracker
    "display": config.DISPLAY_BAND_HZ,  # the waterfall
}


@dataclass
class Bands:
    filtered: dict[str, np.ndarray]  # band name -> (n, n_channels) float64, in data units
    normalised: dict[str, np.ndarray]  # the same divided by each channel's noise level (float32)


class Preprocessor:
    def __init__(self, n_channels: int, fs: float = config.FS_HZ, remove_common_mode: bool = True):
        self.fs = fs
        self.remove_common_mode = remove_common_mode
        self.sos = {name: butter(config.FILTER_ORDER, band, btype="band", fs=fs, output="sos")
                    for name, band in BANDS.items()}
        self.zi = {name: np.zeros((sos.shape[0], 2, n_channels)) for name, sos in self.sos.items()}
        self.level: dict[str, np.ndarray] = {}
        self._block_level: dict[str, np.ndarray] = {}
        self._block_s = 0.0
        self.usable = np.ones(n_channels, dtype=bool)

    def process(self, block: np.ndarray, busy: np.ndarray | None = None) -> Bands:
        """busy: channels currently carrying an event. They are left out of the common-mode
        estimate, because during a big quake the "shared noise" would otherwise be the quake."""
        x = np.nan_to_num(np.asarray(block, dtype=np.float64))
        if self.remove_common_mode:
            quiet = self.usable if busy is None else self.usable & ~busy
            if quiet.sum() >= config.COMMON_MODE_MIN_QUIET * len(quiet):
                x = x - np.median(x[:, quiet], axis=1, keepdims=True)
        self._block_s = len(x) / self.fs
        filtered, normalised = {}, {}
        for name, sos in self.sos.items():
            y, self.zi[name] = sosfilt(sos, x, axis=0, zi=self.zi[name])
            now = np.abs(y).mean(axis=0)
            if name not in self.level:
                self.level[name] = now.copy()  # warm start from the first block
            self._block_level[name] = now
            filtered[name] = y
            normalised[name] = (y / np.maximum(self.level[name], 1e-12)).astype(np.float32)
        self._update_mask()
        return Bands(filtered, normalised)

    def update_noise(self, frozen: np.ndarray) -> None:
        """Advance each channel's noise level, except channels busy with an event (frozen)."""
        keep = np.exp(-self._block_s / config.NOISE_TAU_S)
        for name, level in self.level.items():
            new = keep * level + (1 - keep) * self._block_level[name]
            level[~frozen] = new[~frozen]

    def _update_mask(self) -> None:
        level = self.level["quake"]
        alive = level > 0
        median = np.median(level[alive]) if alive.any() else 0.0
        self.usable = alive & (level <= config.MASK_NOISY_FACTOR * median)
