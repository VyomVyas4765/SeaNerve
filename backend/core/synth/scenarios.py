"""Named recordings and the two cable geometries they use."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from core.geo import CablePath, from_local_km, to_local_km
from core.synth.events import Anchor, Quake, Swell, Vessel

CABLE = "cani_car_nicobar"


@dataclass(frozen=True)
class Geometry:
    path: str
    channel0_km: float
    dx_m: float
    n_channels: int
    shore_km: float

    @property
    def end_km(self) -> float:
        return self.channel0_km + (self.n_channels - 1) * self.dx_m / 1000.0


def _car_nicobar_km() -> float:
    return float(CablePath.load(CABLE).vertex_km[1])


def india_200km(n_channels: int = 1000) -> Geometry:
    """One interrogator at Car Nicobar looking 100 km each way; channel 500 sits at Car Nicobar."""
    cn = _car_nicobar_km()
    return Geometry(CABLE, cn - 100.0, 200.0, n_channels, cn)


def near_shore_10km(n_channels: int = 1000) -> Geometry:
    """10 km just south of the Car Nicobar landing at 10 m spacing, for ships and anchors."""
    cn = _car_nicobar_km()
    return Geometry(CABLE, cn + 5.0, 10.0, n_channels, cn)


@dataclass
class Scenario:
    id: str
    title: str
    geometry: Geometry
    duration_s: float
    seed: int
    events: list = field(default_factory=list)
    noisy_fraction: float = 0.01
    dead_fraction: float = 0.005
    remove_common_mode: bool = True
    start_time: str = "2026-10-10T00:00:00Z"


def car_nicobar_m7() -> Scenario:
    return Scenario("car_nicobar_m7", "Simulated M7.0 near Car Nicobar", india_200km(), 120.0, 7,
                    [Swell(amp=3.0), Quake(10.0, 8.7, 92.9, 20.0, 7.0)])


def vessel_crossing() -> Scenario:
    g = near_shore_10km()
    x0 = g.channel0_km + 2.0
    ship = Vessel(knots_s=(0.0, 120.0), knots_km=(x0, x0 + 0.48), start_s=0.0, end_s=120.0)
    return Scenario("vessel_crossing", "Simulated ship crossing the cable at 4 m/s", g, 120.0, 11,
                    [Swell(amp=3.0), ship])


def anchor_drag() -> Scenario:
    g = near_shore_10km()
    x0 = g.channel0_km + 4.0
    ship = Vessel(knots_s=(0.0, 25.0, 45.0, 120.0),
                  knots_km=(x0, x0 + 0.075, x0 + 0.105, x0 + 0.105), start_s=0.0, end_s=120.0)
    drag = Anchor(knots_s=(50.0, 110.0), knots_km=(x0 + 0.105, x0 + 0.141), start_s=50.0, end_s=110.0)
    return Scenario("anchor_drag", "Simulated ship stopping and dragging its anchor", g, 120.0, 13,
                    [Swell(amp=3.0), ship, drag])


def quiet(duration_s: float = 600.0) -> Scenario:
    return Scenario("quiet", "Simulated quiet sea: noise and swell only", india_200km(), duration_s,
                    17, [Swell(amp=3.0)])


def random_scenario(seed: int, n_channels: int = 1000, duration_s: float = 90.0) -> Scenario:
    """A random class with random parameters, for classifier patches and evaluation."""
    rng = np.random.default_rng(seed)
    kind = str(rng.choice(["earthquake", "vessel", "anchor", "noise"]))
    events: list = [Swell(amp=float(rng.uniform(0.0, 4.0)))]
    if kind == "earthquake":
        g = india_200km(n_channels)
        path = CablePath.load(g.path)
        km = rng.uniform(g.channel0_km, g.end_km)
        (la, lo), (la2, lo2) = (path.point_at(km), path.point_at(km + 1.0))
        dx, dy = to_local_km(la2, lo2, la, lo)
        norm = np.hypot(dx, dy)
        offset = rng.uniform(10.0, 100.0) * rng.choice([-1.0, 1.0])
        lat, lon = from_local_km(-dy / norm * offset, dx / norm * offset, la, lo)
        events.append(Quake(float(rng.uniform(5.0, 20.0)), float(lat), float(lon),
                            float(rng.uniform(5.0, 40.0)), float(rng.uniform(3.5, 7.0))))
    else:
        g = near_shore_10km(n_channels) if kind in ("vessel", "anchor") else india_200km(n_channels)
        margin = min(1.0, (g.end_km - g.channel0_km) / 4)
        if kind == "vessel":
            speed = rng.uniform(2.0, 8.0) * rng.choice([-1.0, 1.0])
            x0 = rng.uniform(g.channel0_km + margin, g.end_km - margin)
            events.append(Vessel((0.0, duration_s), (x0, x0 + speed * duration_s / 1000.0),
                                 0.0, duration_s, amp=float(rng.uniform(3.0, 10.0))))
        elif kind == "anchor":
            speed = rng.uniform(0.3, 1.0)
            start = rng.uniform(5.0, 30.0)
            end = min(duration_s, start + rng.uniform(20.0, 60.0))
            x0 = rng.uniform(g.channel0_km + margin, g.end_km - margin)
            events.append(Anchor((start, end), (x0, x0 + speed * (end - start) / 1000.0), start, end,
                                 amp=float(rng.uniform(6.0, 20.0))))
    return Scenario(f"random-{seed}", f"Random {kind} (seed {seed})", g, duration_s, seed, events)


NAMED = {
    "car_nicobar_m7": car_nicobar_m7,
    "vessel_crossing": vessel_crossing,
    "anchor_drag": anchor_drag,
    "quiet": quiet,
}


def get(scenario_id: str) -> Scenario:
    if scenario_id.startswith("random-"):
        return random_scenario(int(scenario_id.removeprefix("random-")))
    return NAMED[scenario_id]()
