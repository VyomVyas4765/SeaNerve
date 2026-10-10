import numpy as np
import pytest

from core import config
from core.contracts import FRAME_HEADER, Alert, Trigger
from core.geo import city, haversine_km
from core.pipeline.detector import blocks
from core.pipeline.engine import StreamEngine
from core.synth.generator import make_context


def run_engine(rec):
    eng = StreamEngine(rec.meta, rec.meta.id)
    outputs = [eng.feed(block) for block in blocks(rec)]
    alerts = [m for o in outputs for m in o.messages if isinstance(m, Alert)]
    return eng, outputs, alerts


@pytest.fixture(scope="module")
def m7(recordings):
    rec, sc = recordings("car_nicobar_m7")
    return rec, sc, *run_engine(rec)


def test_alert_goes_preliminary_then_updated_then_final(m7):
    *_, alerts = m7
    assert alerts[0].status == "preliminary" and alerts[0].detected_at_s <= 18.0
    assert any(a.status == "updated" for a in alerts)
    assert alerts[-1].status == "final"
    assert [a.rev for a in alerts] == list(range(1, len(alerts) + 1))


def test_s_pick_distance_and_origin(m7):
    rec, sc, _, _, alerts = m7
    quake = sc.events[-1]
    ctx = make_context(sc)
    tp, ts = quake.arrivals(ctx)
    apex = int(np.argmin(tp))
    final = alerts[-1]
    assert abs(final.picks.p_s - tp[apex]) < 0.3
    assert abs(final.picks.s_s - ts[apex]) < 0.3
    true_distance = quake.hypocentral_km(ctx)[apex]
    assert abs(final.location.distance_km - true_distance) / true_distance < 0.10
    assert abs(final.origin_time_s - quake.origin_s) < 1.0


def test_port_blair_countdown_and_magnitude(m7):
    _, sc, _, _, alerts = m7
    quake = sc.events[-1]
    pb = city("Port Blair")
    r = np.hypot(haversine_km(quake.lat, quake.lon, pb.lat, pb.lon), quake.depth_km)
    true_s = quake.origin_s + config.travel_time(r, "S")
    warning = next(w for w in alerts[-1].warnings if w.city == "Port Blair")
    assert abs(warning.s_arrival_s - true_s) < 2.0
    assert warning.s_arrival_s - alerts[0].detected_at_s > 2 * (warning.s_arrival_s - warning.land_station_alert_s)
    assert abs(alerts[-1].magnitude.value - quake.magnitude) < 0.5


def test_messages_and_frames_follow_the_contracts(m7):
    rec, _, eng, outputs, _ = m7
    for o in outputs:
        rows, cols, t0 = FRAME_HEADER.unpack_from(o.frame)
        assert (rows, cols) == (10, eng.display.cols)
        assert len(o.frame) == FRAME_HEADER.size + rows * cols
        for m in o.messages:
            type(m).model_validate(m.to_json())
    assert isinstance(eng.hello().to_json()["cities"], list)


@pytest.mark.parametrize("scenario_id", ["vessel_crossing", "anchor_drag", "quiet"])
def test_no_quake_alerts_without_a_quake(recordings, scenario_id):
    rec, _ = recordings(scenario_id)
    _, outputs, alerts = run_engine(rec)
    assert alerts == []
    assert all(not m.passed for o in outputs for m in o.messages if isinstance(m, Trigger))
