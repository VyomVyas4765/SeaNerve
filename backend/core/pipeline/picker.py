"""S pick: line up the channels nearest the source on their P arrival and find where S kicks in.

P at each channel comes from the gate's fitted arrival curve. Averaging 50 channels' |amplitude|,
aligned on P, gives one clean envelope; S is the first strong onset in it at least 1 s after P
whose amplitude reaches twice the P level. PhaseNet-DAS could replace this behind the same call.
"""

from __future__ import annotations

import numpy as np

from core import config
from core.pipeline.buffer import RingBuffer

PRE_S = 2.0
MAX_AFTER_P_S = 60.0


def _trailing_mean(x: np.ndarray, n: int) -> np.ndarray:
    c = np.concatenate([[0.0], np.cumsum(x)])
    i = np.arange(1, len(x) + 1)
    lo = np.maximum(i - n, 0)
    return (c[i] - c[lo]) / (i - lo)


def pick_s(buf: RingBuffer, p_times: np.ndarray, channels: np.ndarray, t_now: float) -> float | None:
    """S minus P gap (s) at the stacked channels, or None if S hasn't shown up clearly yet."""
    fs = buf.fs
    after = min(MAX_AFTER_P_S, t_now - float(np.max(p_times[channels])))
    if after < 2.0:
        return None
    n_pre, n = int(PRE_S * fs), int((PRE_S + after) * fs)
    stack, used = np.zeros(n), 0
    for ch in channels:
        seg = buf.get(p_times[ch] - PRE_S, n, int(ch))
        if seg is not None:
            stack += np.abs(seg)
            used += 1
    if used == 0:
        return None
    env = np.convolve(stack / used, np.ones(int(0.1 * fs)) / int(0.1 * fs), mode="same")
    tau = (np.arange(n) - n_pre) / fs
    p_level = env[(tau >= 0) & (tau <= 1.0)].max()

    energy = env**2
    ratio = _trailing_mean(energy, int(config.S_STA_S * fs)) / (
        _trailing_mean(energy, int(config.S_LTA_S * fs)) + 1e-30)
    look = int(1.0 * fs)
    for i in np.flatnonzero((tau >= 1.0) & (ratio > config.S_TRIGGER_ON)):
        if i + look > n:
            return None  # wait for a second more data before judging this onset
        if env[i:i + look].max() >= 2.0 * p_level:
            return float(tau[i] - config.S_ONSET_DELAY_S)
    return None
