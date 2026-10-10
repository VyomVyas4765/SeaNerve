"""Physics gate: did this disturbance sweep along the cable the way a seismic wave does?

Four checks on the trigger onsets from the last 15 s:
  coverage  enough of the usable channels triggered
  span      the triggered stretch is long (half the array or 5 km, whichever is smaller)
  speed     onsets move along the cable faster than 1 km/s
  fit       the onsets follow one quake's arrival curve

For cables with known positions the fit tries every point on a map grid (several depths) and keeps
the one whose predicted P times best explain the onsets. That works on a bent cable and gives the
epicentre directly. For arrays with unknown positions it fits a smooth curve along the cable.
"""

from __future__ import annotations

import warnings

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from core import config
from core.contracts import Epicentre, LatLon, RecordingMeta, Trigger
from core.geo import from_local_km, haversine_km, to_local_km

MAX_SPEED_KMS = 999.0  # reported instead of infinity (onsets on many channels at once)
CURVE_POINTS = 60


class PhysicsGate:
    def __init__(self, meta: RecordingMeta, positions=None):
        self.n = meta.n_channels
        self.dx_km = meta.dx_m / 1000.0
        self.vp, self.vs = meta.velocity.vp_kms, meta.velocity.vs_kms
        self.min_span_km = min(self.n * self.dx_km / 2, config.GATE_MIN_SPAN_KM)
        self.has_map = positions is not None
        if self.has_map:
            self.lat, self.lon = (np.asarray(v, dtype=float) for v in positions)
            self.lat0, self.lon0 = float(np.mean(self.lat)), float(np.mean(self.lon))
            self.cx, self.cy = to_local_km(self.lat, self.lon, self.lat0, self.lon0)
        self._cache: tuple[bytes, dict] | None = None  # skip the fit when the onsets haven't changed
        self._warm: tuple[float, float, float] | None = None  # last good epicentre (x, y) and when

    def evaluate(self, t_now: float, onsets: np.ndarray, usable: np.ndarray,
                 active: np.ndarray | None = None) -> Trigger | None:
        """active: channels still triggered. Their onsets count however old, so the channels
        nearest the source (which trigger first) keep anchoring the fit while the wave sweeps on."""
        recent = onsets >= t_now - config.GATE_WINDOW_S
        if active is not None:
            recent |= active
        recent &= usable & np.isfinite(onsets)
        idx = np.flatnonzero(recent)
        if len(idx) < config.GATE_MIN_CHANNELS:
            return None
        t = self._smooth(onsets, recent, idx)
        coverage = len(idx) / max(int(usable.sum()), 1)
        span_km = (idx[-1] - idx[0]) * self.dx_km
        speed = self._speed(idx, t)
        key = idx.tobytes() + np.round(t, 3).tobytes()
        if self._cache and self._cache[0] == key:
            fit = self._cache[1]
        else:
            fit = self._fit_map(idx, t, t_now) if self.has_map else self._fit_curve(idx, t)
            self._cache = (key, fit)

        fails = []
        if coverage < config.GATE_MIN_COVERAGE:
            fails.append(f"coverage {coverage:.2f} < {config.GATE_MIN_COVERAGE:.2f}")
        if span_km < self.min_span_km:
            fails.append(f"span {span_km:.1f} km < {self.min_span_km:.1f} km")
        if speed < config.GATE_MIN_SPEED_KMS:
            fails.append(f"speed {speed:.2f} km/s < {config.GATE_MIN_SPEED_KMS:.1f} km/s")
        if fit["inliers"] < config.GATE_MIN_INLIERS:
            fails.append(f"fit {fit['inliers']:.0%} of onsets on the curve < "
                         f"{config.GATE_MIN_INLIERS:.0%}")

        return Trigger(
            t_s=round(t_now, 3),
            passed=not fails,
            reason="; ".join(fails) or "pass",
            coverage=round(coverage, 3),
            span_km=round(span_km, 2),
            apparent_velocity_kms=round(speed, 2),
            inlier_fraction=round(fit["inliers"], 3),
            channels=(int(idx[0]), int(idx[-1])),
            curve=fit["curve"],
            origin_time_s=fit.get("t0"),
            epicentre=fit.get("epicentre"),
            alt=fit.get("alt"),
            ambiguous=fit.get("ambiguous", False),
        )

    # --- checks ------------------------------------------------------------------------------

    def _smooth(self, onsets, recent, idx) -> np.ndarray:
        """Median of the recent onsets within 15 channels of each triggered channel."""
        half = config.GATE_SMOOTH_CHANNELS // 2
        vals = np.pad(np.where(recent, onsets, np.nan), half, constant_values=np.nan)
        windows = sliding_window_view(vals, 2 * half + 1)[idx]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            return np.nanmedian(windows, axis=1)

    def _speed(self, idx, t) -> float:
        """Median along-cable speed between onsets about a tenth of the triggered set apart."""
        k = max(1, len(idx) // 10)
        dx = (idx[k:] - idx[:-k]) * self.dx_km
        dt = np.abs(t[k:] - t[:-k])
        with np.errstate(divide="ignore"):
            speeds = np.where(dt > 0, dx / dt, np.inf)
        return float(min(np.median(speeds), MAX_SPEED_KMS))

    # --- fits --------------------------------------------------------------------------------

    def _epi_km(self, gx, gy, ch):
        """Epicentral distance from each grid point (rows) to each channel in ch (columns).

        The grid is laid out in flat km, but distances are great-circle, the same as the
        generator's: the flat shortcut alone is off by up to 0.13 s at 150 km.
        """
        glat, glon = from_local_km(gx, gy, self.lat0, self.lon0)
        return haversine_km(glat[:, None], glon[:, None], self.lat[ch][None, :], self.lon[ch][None, :])

    def _p_times(self, gx, gy, depth, ch):
        return config.travel_time(np.hypot(self._epi_km(gx, gy, ch), depth), "P", vp=self.vp)

    def _grid_cost(self, gx, gy, ch, t):
        """Best depth, origin time and robust misfit for each grid point.

        A small penalty per km away from the nominal depth breaks the tie between "deeper and
        closer" and "shallower and further" while only a few channels near the source have
        triggered; once the wave has swept further the data overrule it.
        """
        epi = self._epi_km(gx, gy, ch)
        best = None
        for depth in config.GATE_DEPTHS_KM:
            tt = config.travel_time(np.hypot(epi, depth), "P", vp=self.vp)
            t0 = np.median(t[None, :] - tt, axis=1)
            cost = np.median(np.abs(t[None, :] - tt - t0[:, None]), axis=1)
            cost = cost + config.GATE_DEPTH_PENALTY_S_PER_KM * abs(depth - config.NOMINAL_DEPTH_KM)
            if best is None:
                best = (cost, np.full_like(cost, depth), t0)
            else:
                better = cost < best[0]
                best = (np.where(better, cost, best[0]), np.where(better, depth, best[1]),
                        np.where(better, t0, best[2]))
        return best

    def _search(self, ch, t, centre, half_width, step, keep: int = 1):
        """Grid points with the lowest misfit, best first: (x, y, depth, t0, cost) each."""
        (x0, x1), (y0, y1) = ((c - h, c + h) for c, h in zip(centre, half_width))
        gx, gy = np.meshgrid(np.arange(x0, x1 + step / 2, step), np.arange(y0, y1 + step / 2, step))
        gx, gy = gx.ravel(), gy.ravel()
        cost, depth, t0 = self._grid_cost(gx, gy, ch, t)
        picked: list[int] = []
        for i in np.argsort(cost):  # best first, skipping points next to one already picked
            if all(np.hypot(gx[i] - gx[j], gy[i] - gy[j]) > 2 * step for j in picked):
                picked.append(int(i))
            if len(picked) == keep:
                break
        return [(gx[i], gy[i], depth[i], t0[i], cost[i]) for i in picked]

    def _fit_map(self, idx, t, t_now: float) -> dict:
        sel = np.unique(np.linspace(0, len(idx) - 1, min(len(idx), config.GATE_MAX_FIT_CHANNELS))
                        .astype(int))
        ch, ts = idx[sel], t[sel]
        x, y = self.cx[ch], self.cy[ch]
        m, coarse, fine = config.GATE_GRID_MARGIN_KM, config.GATE_GRID_COARSE_KM, config.GATE_GRID_FINE_KM
        # Coarse grid over the whole area, then a fine grid around each of the best coarse points
        # (the misfit has long narrow valleys where offset trades against depth), then a last
        # 0.5 km pass around the winner. While an event is under way, start from the last answer
        # and its mirror instead of the whole area: same result, a fraction of the work.
        if self._warm and t_now - self._warm[2] <= config.GATE_WARM_START_S:
            wx, wy, _ = self._warm
            candidates = [(wx, wy), self._mirror(wx, wy)]
        else:
            area = ((x.min() + x.max()) / 2, (y.min() + y.max()) / 2)
            half = ((x.max() - x.min()) / 2 + m, (y.max() - y.min()) / 2 + m)
            candidates = self._search(ch, ts, area, half, coarse, keep=config.GATE_REFINE_CANDIDATES)
        refined = [self._search(ch, ts, (cx, cy), (coarse, coarse), fine)[0] for cx, cy, *_ in candidates]
        best = min(refined, key=lambda c: c[4])
        # A cable can't fully tell left from right: also search around the mirror image of the
        # best point, then compare the best fit on each side of the cable.
        mx, my = self._mirror(best[0], best[1])
        refined.append(self._search(ch, ts, (mx, my), (coarse, coarse), fine)[0])
        best_side = self._side(best[0], best[1])
        others = [c for c in refined if self._side(c[0], c[1]) != best_side]
        other = min(others, key=lambda c: c[4]) if others else None
        ambiguous = other is not None and bool(other[4] <= 1.25 * best[4] + 0.02)
        if ambiguous and config.TRENCH_SIDE == "west":
            lon_best = from_local_km(best[0], best[1], self.lat0, self.lon0)[1]
            lon_other = from_local_km(other[0], other[1], self.lat0, self.lon0)[1]
            if lon_other < lon_best:
                best, other = other, best
        ex, ey, depth, t0, cost = self._search(ch, ts, (best[0], best[1]), (fine, fine), fine / 4)[0]
        lat, lon = from_local_km(ex, ey, self.lat0, self.lon0)
        if ambiguous:
            mlat, mlon = from_local_km(other[0], other[1], self.lat0, self.lon0)

        resid = ts - t0 - self._p_times(np.array([ex]), np.array([ey]), depth, ch)[0]
        inliers = float(np.mean(np.abs(resid) < config.GATE_FIT_TOL_S))
        self._warm = (ex, ey, t_now) if inliers >= config.GATE_MIN_INLIERS else None
        curve_ch = np.unique(np.linspace(idx[0], idx[-1], CURVE_POINTS).astype(int))
        curve_t = t0 + self._p_times(np.array([ex]), np.array([ey]), depth, curve_ch)[0]
        return {
            "inliers": inliers,
            "t0": round(float(t0), 3),
            "epicentre": Epicentre(lat=round(float(lat), 4), lon=round(float(lon), 4),
                                   depth_km=float(depth)),
            "alt": LatLon(lat=round(float(mlat), 4), lon=round(float(mlon), 4)) if ambiguous else None,
            "ambiguous": ambiguous,
            "curve": [(int(c), round(float(v), 3)) for c, v in zip(curve_ch, curve_t)],
        }

    def _local_frame(self, ex, ey):
        """Nearest channel, the cable's unit direction there, and the point relative to it."""
        i = int(np.argmin(np.hypot(self.cx - ex, self.cy - ey)))
        a, b = max(i - 5, 0), min(i + 5, self.n - 1)
        dx, dy = self.cx[b] - self.cx[a], self.cy[b] - self.cy[a]
        norm = np.hypot(dx, dy) or 1.0
        return i, dx / norm, dy / norm, ex - self.cx[i], ey - self.cy[i]

    def _mirror(self, ex, ey):
        """Reflect a point across the cable's local direction at the nearest channel."""
        i, ux, uy, px, py = self._local_frame(ex, ey)
        along = px * ux + py * uy
        return self.cx[i] + 2 * along * ux - px, self.cy[i] + 2 * along * uy - py

    def _side(self, ex, ey) -> bool:
        """Which side of the cable a point lies on (True = left of the channel direction)."""
        _, ux, uy, px, py = self._local_frame(ex, ey)
        return bool(ux * py - uy * px > 0)

    def _fit_curve(self, idx, t) -> dict:
        """Unknown positions: a quadratic in distance along the cable (nearly straight here)."""
        km = idx * self.dx_km
        deg = 2 if len(idx) > 3 else 1
        coef = np.polyfit(km, t, deg)
        inliers = float(np.mean(np.abs(t - np.polyval(coef, km)) < config.GATE_FIT_TOL_S))
        curve_ch = np.unique(np.linspace(idx[0], idx[-1], CURVE_POINTS).astype(int))
        curve_t = np.polyval(coef, curve_ch * self.dx_km)
        return {
            "inliers": inliers,
            "curve": [(int(c), round(float(v), 3)) for c, v in zip(curve_ch, curve_t)],
        }
