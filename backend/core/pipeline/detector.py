"""The detection front end: clean -> trigger -> physics gate, fed one block at a time.

The stream engine (server side) wraps this and adds picks, location, warnings and the tracker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np

from core.contracts import RecordingMeta, Trigger
from core.geo import channel_positions
from core.pipeline.gate import PhysicsGate
from core.pipeline.preprocess import Bands, Preprocessor
from core.pipeline.trigger import StaLta
from core.recording import Recording


@dataclass
class Step:
    t_end: float
    bands: Bands
    new_onsets: np.ndarray
    trigger: Trigger | None


class Detector:
    def __init__(self, meta: RecordingMeta):
        self.meta = meta
        self.fs = meta.fs_hz
        self.pre = Preprocessor(meta.n_channels, meta.fs_hz, meta.remove_common_mode)
        self.stalta = StaLta(meta.n_channels, meta.fs_hz)
        self.gate = PhysicsGate(meta, channel_positions(meta))
        self.t = 0.0  # stream time of the next sample

    def feed(self, block: np.ndarray) -> Step:
        t0 = self.t
        bands = self.pre.process(block, busy=self.stalta.triggered)
        new = self.stalta.process(bands.filtered["quake"], t0)
        self.pre.update_noise(frozen=self.stalta.triggered)
        self.t = t0 + len(block) / self.fs
        trigger = self.gate.evaluate(self.t, self.stalta.onset, self.pre.usable,
                                     active=self.stalta.triggered)
        return Step(self.t, bands, new, trigger)


def blocks(rec: Recording, block_s: float = 1.0) -> Iterator[np.ndarray]:
    n = int(round(block_s * rec.meta.fs_hz))
    for i0 in range(0, rec.meta.n_samples, n):
        yield np.asarray(rec.data[i0:i0 + n])
