"""Distances, the cable path, and where each channel sits on the map."""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np

from core.config import GEO_DIR
from core.contracts import City, RecordingMeta

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance; broadcasts over numpy arrays."""
    la1, lo1, la2, lo2 = (np.radians(np.asarray(v, dtype=float)) for v in (lat1, lon1, lat2, lon2))
    h = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    d = 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(h))
    return d if d.ndim else float(d)


def to_local_km(lat, lon, lat0: float, lon0: float):
    """Flat east/north km around (lat0, lon0). Good to well under 1% over a few hundred km."""
    x = (np.asarray(lon) - lon0) * 111.32 * np.cos(np.radians(lat0))
    y = (np.asarray(lat) - lat0) * 110.57
    return x, y


def from_local_km(x, y, lat0: float, lon0: float):
    lat = lat0 + np.asarray(y) / 110.57
    lon = lon0 + np.asarray(x) / (111.32 * np.cos(np.radians(lat0)))
    return lat, lon


class CablePath:
    """A polyline of (lat, lon) vertices with cumulative distance along it."""

    def __init__(self, path_id: str, lats, lons):
        self.id = path_id
        self.lats = np.asarray(lats, dtype=float)
        self.lons = np.asarray(lons, dtype=float)
        seg = haversine_km(self.lats[:-1], self.lons[:-1], self.lats[1:], self.lons[1:])
        self.vertex_km = np.concatenate([[0.0], np.cumsum(seg)])

    @property
    def length_km(self) -> float:
        return float(self.vertex_km[-1])

    def point_at(self, km):
        """Latitude and longitude at distance km along the path (clamped to its ends)."""
        km = np.clip(np.asarray(km, dtype=float), 0.0, self.length_km)
        return np.interp(km, self.vertex_km, self.lats), np.interp(km, self.vertex_km, self.lons)

    @classmethod
    def load(cls, path_id: str) -> CablePath:
        return _load_path(path_id)


@lru_cache
def _load_path(path_id: str) -> CablePath:
    features = json.loads((GEO_DIR / "cani.geojson").read_text())["features"]
    for f in features:
        if f["properties"]["id"] == path_id:
            lons, lats = zip(*f["geometry"]["coordinates"])
            return CablePath(path_id, lats, lons)
    raise KeyError(f"no cable path {path_id!r} in cani.geojson")


def channel_km(meta: RecordingMeta) -> np.ndarray:
    """Distance of each channel along the cable path."""
    return meta.cable.channel0_km + np.arange(meta.n_channels) * meta.dx_m / 1000.0


def channel_positions(meta: RecordingMeta):
    """(lat, lon) arrays per channel, or None when the array's position is unknown."""
    if meta.cable.path is None:
        return None
    return CablePath.load(meta.cable.path).point_at(channel_km(meta))


@lru_cache
def cities() -> tuple[City, ...]:
    return tuple(City(**c) for c in json.loads((GEO_DIR / "cities.json").read_text()))


def city(name: str) -> City:
    return next(c for c in cities() if c.name == name)
