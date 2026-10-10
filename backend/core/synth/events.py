"""Signal models for what a seabed fibre picks up: quakes, ships, dragged anchors, swell, noise.

Each event is a small dataclass. `bind(ctx, rng)` does the per-recording set-up and returns a
`render(t)` function that gives the event's contribution for a chunk of sample times, shaped
(len(t), n_channels). The generator adds the chunks up, so memory stays flat for long recordings.
Amplitudes are in units of the background noise level.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from scipy.signal import butter, sosfiltfilt

from core import config
from core.contracts import TruthEvent
from core.geo import haversine_km

Render = Callable[[np.ndarray], np.ndarray]


@dataclass
class Context:
    fs: float
    x_km: np.ndarray  # distance of each channel along the cable
    lat: np.ndarray
    lon: np.ndarray
    shore_km: float  # where the cable lands; swell is strongest here


def _taper(t: np.ndarray, start: float, end: float, ramp: float) -> np.ndarray:
    """1 inside [start, end], with smooth cosine ramps of length `ramp` at both ends."""
    up = np.clip((t - start) / ramp, 0.0, 1.0)
    down = np.clip((end - t) / ramp, 0.0, 1.0)
    return (0.5 - 0.5 * np.cos(np.pi * up)) * (0.5 - 0.5 * np.cos(np.pi * down))


def _along_cable(ctx: Context, centre_km: np.ndarray, width_m: float) -> np.ndarray:
    """Gaussian footprint along the cable, (len(centre_km), n_channels). width_m is the FWHM."""
    sigma_km = width_m / 1000.0 / 2.355
    return np.exp(-0.5 * ((ctx.x_km[None, :] - centre_km[:, None]) / sigma_km) ** 2)


class Noise:
    """White noise per channel, a slow random walk, and a term shared by the whole cable."""

    def __init__(self, n_channels: int, rng: np.random.Generator, noisy: np.ndarray,
                 walk_step: float = 0.02, common: float = 0.5, noisy_factor: float = 8.0):
        self.rng = rng
        self.n_channels = n_channels
        self.noisy = noisy
        self.walk_step = walk_step
        self.common = common
        self.noisy_factor = noisy_factor
        self.walk = np.zeros(n_channels, dtype=np.float32)

    def render(self, n: int) -> np.ndarray:
        rng = self.rng
        white = rng.standard_normal((n, self.n_channels), dtype=np.float32)
        white[:, self.noisy] *= self.noisy_factor
        steps = rng.standard_normal((n, self.n_channels), dtype=np.float32) * self.walk_step
        walk = self.walk + np.cumsum(steps, axis=0)
        self.walk = walk[-1]
        common = rng.standard_normal(n, dtype=np.float32) * self.common
        return white + walk + common[:, None]


def _burst(tau: np.ndarray, decay_s: float, freqs: np.ndarray, phases: np.ndarray) -> np.ndarray:
    """A 2-8 Hz wave train with a sharp onset at tau=0 and an exponential coda."""
    on = tau >= 0
    tau = np.where(on, tau, 0.0)
    env = (1.0 - np.exp(-tau / 0.03)) * np.exp(-tau / decay_s)
    wave = np.zeros_like(tau)
    for f, ph in zip(freqs, phases):
        wave += np.sin(2 * np.pi * f * tau + ph)
    return np.where(on, env * wave / len(freqs), 0.0)


@dataclass
class Quake:
    origin_s: float
    lat: float
    lon: float
    depth_km: float
    magnitude: float

    def hypocentral_km(self, ctx: Context) -> np.ndarray:
        epi = haversine_km(self.lat, self.lon, ctx.lat, ctx.lon)
        return np.hypot(epi, self.depth_km)

    def arrivals(self, ctx: Context) -> tuple[np.ndarray, np.ndarray]:
        """True P and S arrival time at every channel."""
        r = self.hypocentral_km(ctx)
        return (self.origin_s + config.travel_time(r, "P"),
                self.origin_s + config.travel_time(r, "S"))

    def bind(self, ctx: Context, rng: np.random.Generator) -> Render:
        r = self.hypocentral_km(ctx)
        tp, ts = self.arrivals(ctx)
        a_s = 10 ** (config.AMP_A * self.magnitude + config.AMP_B * np.log10(r) + config.AMP_C)
        a_p = a_s * config.P_TO_S_RATIO
        freqs = rng.uniform(2.0, 8.0, 3)
        phases = rng.uniform(0, 2 * np.pi, 3)
        decay_p = float(np.clip(0.4 * 10 ** (0.2 * (self.magnitude - 3)), 0.4, 6.0))
        decay_s = 1.5 * decay_p

        def render(t: np.ndarray) -> np.ndarray:
            if t[-1] < tp.min():
                return np.zeros((len(t), len(r)), dtype=np.float32)
            p = a_p * _burst(t[:, None] - tp[None, :], decay_p, freqs, phases)
            s = a_s * _burst(t[:, None] - ts[None, :], decay_s, freqs, phases + 1.0)
            return (p + s).astype(np.float32)

        return render

    def truth(self, ctx: Context) -> TruthEvent:
        return TruthEvent(cls="earthquake", origin_s=self.origin_s, lat=self.lat, lon=self.lon,
                          depth_km=self.depth_km, magnitude=self.magnitude)


@dataclass
class Vessel:
    """Engine and propeller tones under a footprint that moves along the cable.

    knots_s / knots_km give the footprint centre over time, so a ship can cruise, slow and stop.
    The speed is the along-cable part of the ship's motion (a ship crossing at an angle).
    """

    knots_s: tuple[float, ...]
    knots_km: tuple[float, ...]
    start_s: float
    end_s: float
    amp: float = 6.0
    width_m: float = 300.0
    ramp_s: float = 10.0

    def bind(self, ctx: Context, rng: np.random.Generator) -> Render:
        n_tones = int(rng.integers(2, 4))
        freqs = rng.uniform(12.0, 35.0, n_tones)
        phases = rng.uniform(0, 2 * np.pi, n_tones)

        def render(t: np.ndarray) -> np.ndarray:
            env = self.amp * _taper(t, self.start_s, self.end_s, self.ramp_s)
            if not env.any():
                return np.zeros((len(t), len(ctx.x_km)), dtype=np.float32)
            tone = sum(np.sin(2 * np.pi * f * t + ph) for f, ph in zip(freqs, phases)) / n_tones
            centre = np.interp(t, self.knots_s, self.knots_km)
            return ((env * tone)[:, None] * _along_cable(ctx, centre, self.width_m)).astype(np.float32)

        return render

    def truth(self, ctx: Context) -> TruthEvent:
        speed = (self.knots_km[1] - self.knots_km[0]) * 1000 / (self.knots_s[1] - self.knots_s[0])
        return TruthEvent(cls="vessel", start_s=self.start_s, end_s=self.end_s,
                          along_cable_km=self.knots_km[0], speed_ms=round(speed, 3))


@dataclass
class Anchor:
    """Irregular broadband scrapes (5-45 Hz, 0.2-1 s each) under a narrow, creeping footprint."""

    knots_s: tuple[float, ...]
    knots_km: tuple[float, ...]
    start_s: float
    end_s: float
    amp: float = 12.0
    width_m: float = 100.0
    rate_hz: float = 3.0

    def bind(self, ctx: Context, rng: np.random.Generator) -> Render:
        fs = ctx.fs
        sos = butter(4, [5.0, 45.0], btype="band", fs=fs, output="sos")
        n_bursts = int(rng.poisson(self.rate_hz * (self.end_s - self.start_s)))
        starts = np.sort(rng.uniform(self.start_s, self.end_s - 0.2, n_bursts))
        bursts = []
        for t0 in starts:
            n = int(rng.uniform(0.2, 1.0) * fs)
            w = sosfiltfilt(sos, rng.standard_normal(n + 200))[100:100 + n]
            w *= np.hanning(n) * self.amp * rng.uniform(0.5, 1.5) / (w.std() + 1e-12)
            bursts.append((int(round(t0 * fs)), w))

        def render(t: np.ndarray) -> np.ndarray:
            i0 = int(round(t[0] * fs))
            i1 = i0 + len(t)
            s = np.zeros(len(t))
            for b0, w in bursts:
                lo, hi = max(b0, i0), min(b0 + len(w), i1)
                if lo < hi:
                    s[lo - i0:hi - i0] += w[lo - b0:hi - b0]
            if not s.any():
                return np.zeros((len(t), len(ctx.x_km)), dtype=np.float32)
            centre = np.interp(t, self.knots_s, self.knots_km)
            return (s[:, None] * _along_cable(ctx, centre, self.width_m)).astype(np.float32)

        return render

    def truth(self, ctx: Context) -> TruthEvent:
        speed = (self.knots_km[-1] - self.knots_km[0]) * 1000 / (self.knots_s[-1] - self.knots_s[0])
        return TruthEvent(cls="anchor", start_s=self.start_s, end_s=self.end_s,
                          along_cable_km=self.knots_km[0], speed_ms=round(speed, 3))


@dataclass
class Swell:
    """0.1-0.3 Hz ocean waves travelling along the cable, fading over the first ~20 km offshore."""

    amp: float = 3.0
    decay_km: float = 20.0

    def bind(self, ctx: Context, rng: np.random.Generator) -> Render:
        comps = [(rng.uniform(0.1, 0.3), rng.uniform(10.0, 20.0), rng.uniform(0, 2 * np.pi))
                 for _ in range(2)]
        offset_m = (ctx.x_km - ctx.shore_km) * 1000.0
        a = self.amp * np.exp(-np.abs(offset_m) / 1000.0 / self.decay_km) / len(comps)

        def render(t: np.ndarray) -> np.ndarray:
            out = np.zeros((len(t), len(ctx.x_km)))
            for f, c, ph in comps:
                out += a[None, :] * np.sin(2 * np.pi * f * (t[:, None] - offset_m[None, :] / c) + ph)
            return out.astype(np.float32)

        return render

    def truth(self, ctx: Context) -> TruthEvent:
        return TruthEvent(cls="swell")
