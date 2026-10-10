"""Distance from the S-P gap, origin time, rough magnitude and city countdowns."""

from __future__ import annotations

import numpy as np

from core import config
from core.contracts import CityWarning
from core.geo import cities, haversine_km


def distance_from_sp(gap_s: float, vp: float, vs: float) -> float:
    """Distance to the source: S and P left together, S fell behind by gap_s."""
    return gap_s * vp * vs / (vp - vs)


def origin_from_p(p_s: float, distance_km: float, vp: float) -> float:
    return p_s - config.travel_time(distance_km, "P", vp=vp)


def magnitude(peaks: np.ndarray, distances_km: np.ndarray) -> float | None:
    """Invert log10(A) = a*M + b*log10(r) + c per channel, then take the median."""
    ok = (peaks > 0) & (distances_km > 0)
    if not ok.any():
        return None
    m = (np.log10(peaks[ok]) - config.AMP_B * np.log10(distances_km[ok]) - config.AMP_C) / config.AMP_A
    return float(np.median(m))


def city_warnings(origin_s: float, lat: float, lon: float, depth_km: float,
                  vp: float, vs: float) -> list[CityWarning]:
    """When S waves reach each city, and when a seismometer in that city would have alerted."""
    out = []
    for c in cities():
        r = float(np.hypot(haversine_km(lat, lon, c.lat, c.lon), depth_km))
        out.append(CityWarning(
            city=c.name,
            distance_km=round(r, 1),
            s_arrival_s=round(origin_s + config.travel_time(r, "S", vs=vs), 2),
            land_station_alert_s=round(origin_s + config.travel_time(r, "P", vp=vp)
                                       + config.LAND_STATION_PROCESSING_S, 2),
        ))
    return sorted(out, key=lambda w: w.s_arrival_s)
