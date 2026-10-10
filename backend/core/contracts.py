"""Data contracts. The generator, pipeline, server and dashboard only meet through these.

Pydantic only (no web imports), so the engine can validate its own output in tests.
`frontend/src/types.ts` mirrors every message by hand; change both together.

Binary waterfall frame (WebSocket binary message):
    16-byte little-endian header: uint32 rows, uint32 cols, float64 stream time of the first row,
    then rows * cols bytes of uint8, row-major, oldest row first. 128 means zero; values are
    signed and log-scaled (see core/pipeline/display.py) so noise is faint and big quakes still
    show structure.
"""

from __future__ import annotations

import struct
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FRAME_HEADER = struct.Struct("<IId")

EventClass = Literal["earthquake", "vessel", "anchor", "noise", "cable_threat"]
TruthClass = Literal["earthquake", "vessel", "anchor", "swell"]
Mode = Literal["scenario", "replay"]


class Model(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    def to_json(self) -> dict:
        """Dict ready for json.dumps, using wire names such as "class"."""
        return self.model_dump(by_alias=True, mode="json")


# --- Recording -------------------------------------------------------------------------------


class CableRef(Model):
    path: str | None = None  # feature id in data/geo/cani.geojson; None when positions are unknown
    channel0_km: float = 0.0  # distance of channel 0 along that path


class Velocity(Model):
    vp_kms: float = 6.5
    vs_kms: float = 3.5


class TruthEvent(Model):
    """What the generator drew. Filled for synthetic recordings only."""

    cls: TruthClass = Field(alias="class")
    origin_s: float | None = None
    start_s: float | None = None
    end_s: float | None = None
    lat: float | None = None
    lon: float | None = None
    depth_km: float | None = None
    magnitude: float | None = None
    along_cable_km: float | None = None
    speed_ms: float | None = None


class Catalog(Model):
    """The catalog entry for a real recording (QuakeFlow attributes or USGS)."""

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    event_id: str | None = None
    event_time: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    depth_km: float | None = None
    magnitude: float | None = None
    magnitude_type: str | None = None


class RecordingMeta(Model):
    id: str
    title: str = ""
    kind: Literal["synthetic", "real"]
    fs_hz: float
    dx_m: float
    n_channels: int
    n_samples: int
    start_time: str
    cable: CableRef = CableRef()
    velocity: Velocity = Velocity()
    remove_common_mode: bool = True
    seed: int | None = None
    truth: list[TruthEvent] = []
    catalog: Catalog | None = None

    @property
    def duration_s(self) -> float:
        return self.n_samples / self.fs_hz


# --- WebSocket messages ----------------------------------------------------------------------


class LatLon(Model):
    lat: float
    lon: float


class Epicentre(LatLon):
    depth_km: float


class City(LatLon):
    name: str


class Hello(Model):
    type: Literal["hello"] = "hello"
    session_id: str = ""  # a dashboard that reconnects to the same session keeps its state
    mode: Mode
    source: str
    title: str
    kind: Literal["synthetic", "real"]
    duration_s: float
    rows_per_s: int
    cols: int
    channels_per_col: int
    km_per_col: float
    dx_m: float
    n_channels: int
    channel0_km: float
    cable_path: str | None
    cities: list[City]
    catalog: Catalog | None = None


class Trigger(Model):
    """The physics gate's verdict, sent every time it evaluates, pass or fail."""

    type: Literal["trigger"] = "trigger"
    t_s: float
    passed: bool
    reason: str
    coverage: float
    span_km: float
    apparent_velocity_kms: float | None = None
    inlier_fraction: float | None = None
    channels: tuple[int, int] | None = None
    curve: list[tuple[int, float]] = []  # (channel, predicted P time) for the waterfall overlay
    origin_time_s: float | None = None
    epicentre: Epicentre | None = None
    alt: LatLon | None = None
    ambiguous: bool = False


class LocalEvent(Model):
    type: Literal["local_event"] = "local_event"
    t_s: float
    track_id: int
    cls: Literal["vessel", "anchor", "noise"] = Field(alias="class")
    position_km: float
    width_m: float
    speed_ms: float
    threat: Literal["info", "watch", "alarm"]
    lat: float | None = None
    lon: float | None = None


class GateSummary(Model):
    coverage: float
    apparent_velocity_kms: float | None
    channels: tuple[int, int]


class Picks(Model):
    p_s: float
    s_s: float | None = None
    method: str = "stalta"


class Location(Model):
    along_cable_km: float | None = None
    distance_km: float | None = None
    lat: float | None = None
    lon: float | None = None
    ambiguous: bool = False
    alt: LatLon | None = None


class Magnitude(Model):
    value: float
    quality: Literal["rough"] = "rough"


class CityWarning(Model):
    city: str
    distance_km: float
    s_arrival_s: float
    land_station_alert_s: float


class Alert(Model):
    """Revised as evidence arrives: preliminary (gate), updated (S pick, classifier), final."""

    type: Literal["alert"] = "alert"
    id: str
    rev: int
    status: Literal["preliminary", "updated", "final", "cancelled"]
    mode: Mode
    source: str
    cls: EventClass = Field(alias="class")
    confidence: float | None = None
    classifier: Literal["rules", "resnet", "pending"] = "pending"
    detected_at_s: float
    origin_time_s: float | None = None
    gate: GateSummary | None = None
    picks: Picks | None = None
    location: Location | None = None
    magnitude: Magnitude | None = None
    warnings: list[CityWarning] = []
    latency_ms: float | None = None


class Status(Model):
    type: Literal["status"] = "status"
    t_s: float
    speed: float
    paused: bool = False
    latency_ms: float | None = None
    stage_ms: dict[str, float] = {}
    data_kept_ratio: float | None = None
    ended: bool = False  # the recording has run out; the clock keeps going for the countdowns
