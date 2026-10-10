"""StreamEngine.feed(block) -> what that second produced: a waterfall frame and messages.

It holds all state (filters, trigger, rolling buffers, the current event), so the same code serves
Replay, Scenario and the tests. An alert is revised as evidence arrives:
  preliminary  the gate passed: class, position along the cable, epicentre and countdowns
  updated      S picked (distance, magnitude) or the epicentre sharpened as the wave swept on
  final        60 s after P, or the cable has gone quiet again
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from core import config
from core.contracts import (Alert, Epicentre, GateSummary, Hello, LatLon, Location, Magnitude, Mode,
                            Picks, RecordingMeta, Trigger)
from core.geo import channel_km, channel_positions, cities, haversine_km
from core.pipeline.buffer import RingBuffer
from core.pipeline.detector import Detector
from core.pipeline.display import ROWS_PER_S, Display
from core.pipeline.locate import city_warnings, distance_from_sp, magnitude, origin_from_p
from core.pipeline.picker import pick_s

BUFFER_S = 75.0
MAGNITUDE_CHANNELS = 200


@dataclass
class Event:
    id: str
    detected_at: float
    gate: GateSummary
    coverage: float
    inliers: float
    p_times: np.ndarray  # predicted P time at every channel, from the gate's fit
    apex: int  # channel the wave reached first
    origin_s: float | None
    epicentre: Epicentre | None = None
    alt: LatLon | None = None
    ambiguous: bool = False
    s_s: float | None = None
    distance_km: float | None = None
    magnitude: float | None = None
    status: str = "preliminary"
    rev: int = 0
    latency_ms: float | None = None
    log: list = field(default_factory=list)

    @property
    def p_s(self) -> float:
        return float(self.p_times[self.apex])


@dataclass
class Output:
    t_end: float
    frame: bytes
    messages: list
    stage_ms: dict[str, float]
    data_kept_ratio: float


class StreamEngine:
    def __init__(self, meta: RecordingMeta, source: str):
        self.meta = meta
        self.source = source
        self.mode: Mode = "scenario" if meta.kind == "synthetic" else "replay"
        self.fs = meta.fs_hz
        self.n = meta.n_channels
        self.vp, self.vs = meta.velocity.vp_kms, meta.velocity.vs_kms
        self.det = Detector(meta)
        self.positions = channel_positions(meta)
        self.ch_km = channel_km(meta)
        self.norm = RingBuffer(BUFFER_S, self.n, self.fs)  # noise-normalised quake band: S picks
        self.raw = RingBuffer(BUFFER_S, self.n, self.fs)  # quake band in data units: magnitude
        self.display = Display(self.n, self.fs)
        self.event: Event | None = None
        self.armed = True
        self.n_events = 0
        self.alerts: dict[str, Alert] = {}
        self.samples_total = 0
        self.samples_kept = 0

    def hello(self, session_id: str = "") -> Hello:
        m = self.meta
        return Hello(
            session_id=session_id, mode=self.mode, source=self.source, title=m.title, kind=m.kind, duration_s=m.duration_s,
            rows_per_s=ROWS_PER_S, cols=self.display.cols, channels_per_col=self.display.step,
            km_per_col=self.display.step * m.dx_m / 1000.0, dx_m=m.dx_m, n_channels=self.n,
            channel0_km=m.cable.channel0_km, cable_path=m.cable.path, cities=list(cities()),
            catalog=m.catalog,
        )

    def feed(self, block: np.ndarray) -> Output:
        start = time.perf_counter()
        t0 = self.det.t
        step = self.det.feed(block)
        detect_ms = (time.perf_counter() - start) * 1000

        self.norm.push(step.bands.normalised["quake"])
        self.raw.push(step.bands.filtered["quake"].astype(np.float32))
        frame = self.display.frame(step.bands.normalised["display"], t0, self.det.pre.usable)
        busy = self.det.stalta.triggered & self.det.pre.usable
        self.samples_total += len(block) * self.n
        self.samples_kept += len(block) * int(busy.sum())

        mid = time.perf_counter()
        messages: list = [step.trigger] if step.trigger else []
        messages += self._update_event(step.trigger, step.t_end, busy.mean(),
                                       latency_ms=(mid - start) * 1000)
        locate_ms = (time.perf_counter() - mid) * 1000
        return Output(step.t_end, frame, messages, {"detect": round(detect_ms, 1), "locate": round(locate_ms, 1)},
                      self.samples_kept / max(self.samples_total, 1))

    # --- event lifecycle ---------------------------------------------------------------------

    def _update_event(self, trig: Trigger | None, t: float, busy_fraction: float,
                      latency_ms: float) -> list[Alert]:
        ev = self.event
        if ev is None:
            if busy_fraction < config.REARM_TRIGGERED_FRACTION:
                self.armed = True
            if self.armed and trig is not None and trig.passed:
                ev = self._start(trig, t, latency_ms)
                return [self._alert(ev)]
            return []

        changed = False
        if trig is not None and trig.passed and trig.coverage > ev.coverage + 0.02:
            self._apply_fit(ev, trig)  # the wave has swept further: a better epicentre
            changed = True
        if ev.s_s is None and t - ev.p_s >= 1.5:
            gap = self._pick_s(ev, t)
            if gap is not None:
                ev.s_s = ev.p_s + gap
                ev.distance_km = distance_from_sp(gap, self.vp, self.vs)
                if ev.epicentre is None:  # no map: origin from the S-P distance instead
                    ev.origin_s = origin_from_p(ev.p_s, ev.distance_km, self.vp)
                ev.status = "updated"
                changed = True
        if ev.s_s is not None:
            m = self._magnitude(ev, t)
            if m is not None and (ev.magnitude is None or abs(m - ev.magnitude) >= 0.1):
                ev.magnitude = m
                changed = True
        if t - ev.p_s >= config.EVENT_FINAL_AFTER_S or (
                t - ev.p_s > 20 and busy_fraction < config.REARM_TRIGGERED_FRACTION):
            ev.status = "final"
            self.event, self.armed = None, False
            changed = True
        return [self._alert(ev)] if changed else []

    def _start(self, trig: Trigger, t: float, latency_ms: float) -> Event:
        self.n_events += 1
        ev = Event(id=f"evt-{self.n_events:04d}", detected_at=t, gate=self._gate_summary(trig),
                   coverage=trig.coverage, inliers=trig.inlier_fraction or 0.0,
                   p_times=np.zeros(self.n), apex=0, origin_s=None, latency_ms=round(latency_ms, 1))
        self._apply_fit(ev, trig)
        self.event = ev
        return ev

    def _gate_summary(self, trig: Trigger) -> GateSummary:
        return GateSummary(coverage=trig.coverage, apparent_velocity_kms=trig.apparent_velocity_kms,
                           channels=trig.channels)

    def _apply_fit(self, ev: Event, trig: Trigger) -> None:
        ev.gate, ev.coverage, ev.inliers = self._gate_summary(trig), trig.coverage, trig.inlier_fraction or 0.0
        if trig.epicentre is not None and self.positions is not None:
            e = trig.epicentre
            lat, lon = self.positions
            r = np.hypot(haversine_km(e.lat, e.lon, lat, lon), e.depth_km)
            ev.p_times = trig.origin_time_s + config.travel_time(r, "P", vp=self.vp)
            ev.epicentre, ev.alt, ev.ambiguous = e, trig.alt, trig.ambiguous
            ev.origin_s = trig.origin_time_s
            if ev.s_s is None:
                ev.distance_km = float(r.min())
        else:  # unknown positions: interpolate the gate's fitted curve along the cable
            ch, tt = zip(*trig.curve)
            ev.p_times = np.interp(np.arange(self.n), ch, tt)
        ev.apex = int(np.argmin(ev.p_times))

    def _pick_s(self, ev: Event, t: float) -> float | None:
        half = config.S_STACK_CHANNELS // 2
        lo, hi = max(ev.apex - half, 0), min(ev.apex + half, self.n)
        chans = np.arange(lo, hi)
        chans = chans[self.det.pre.usable[chans]]
        return pick_s(self.norm, ev.p_times, chans, t) if len(chans) else None

    def _magnitude(self, ev: Event, t: float) -> float | None:
        """Median per-channel magnitude over channels whose S wave has fully passed by."""
        if ev.epicentre is not None:
            lat, lon = self.positions
            e = ev.epicentre
            r = np.hypot(haversine_km(e.lat, e.lon, lat, lon), e.depth_km)
            s_times = ev.origin_s + config.travel_time(r, "S", vs=self.vs)
        else:
            r = np.full(self.n, ev.distance_km)
            s_times = np.full(self.n, ev.s_s)
        ready = np.flatnonzero(self.det.pre.usable & (s_times + 3.0 <= t)
                               & (s_times - 0.5 >= self.raw.t_start))
        if len(ready) == 0:
            return None
        ready = ready[np.unique(np.linspace(0, len(ready) - 1, min(len(ready), MAGNITUDE_CHANNELS)).astype(int))]
        n = int(3.5 * self.fs)
        peaks = np.array([np.abs(self.raw.get(s_times[c] - 0.5, n, int(c))).max() for c in ready])
        m = magnitude(peaks, r[ready])
        return None if m is None else round(m, 1)

    def _alert(self, ev: Event) -> Alert:
        ev.rev += 1
        warnings = []
        if ev.epicentre is not None and ev.origin_s is not None:
            warnings = city_warnings(ev.origin_s, ev.epicentre.lat, ev.epicentre.lon,
                                     ev.epicentre.depth_km, self.vp, self.vs)
        alert = Alert(
            id=ev.id, rev=ev.rev, status=ev.status, mode=self.mode, source=self.source,
            cls="earthquake", confidence=round(ev.inliers, 2), classifier="rules",
            detected_at_s=round(ev.detected_at, 2),
            origin_time_s=None if ev.origin_s is None else round(ev.origin_s, 2),
            gate=ev.gate,
            picks=Picks(p_s=round(ev.p_s, 2), s_s=None if ev.s_s is None else round(ev.s_s, 2)),
            location=Location(
                along_cable_km=round(float(self.ch_km[ev.apex]), 2),
                distance_km=None if ev.distance_km is None else round(ev.distance_km, 1),
                lat=ev.epicentre.lat if ev.epicentre else None,
                lon=ev.epicentre.lon if ev.epicentre else None,
                ambiguous=ev.ambiguous, alt=ev.alt),
            magnitude=None if ev.magnitude is None else Magnitude(value=ev.magnitude),
            warnings=warnings,
            latency_ms=ev.latency_ms,
        )
        self.alerts[ev.id] = alert
        return alert
