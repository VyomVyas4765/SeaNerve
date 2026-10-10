import json

import numpy as np
from scipy.signal import butter, sosfilt

from core.contracts import Alert, RecordingMeta
from core.geo import CablePath, channel_positions, city, haversine_km
from core.synth import scenarios
from core.synth.generator import build_recording, make_context


def test_same_seed_gives_identical_array(tmp_path):
    sc = scenarios.random_scenario(5, n_channels=100, duration_s=20.0)
    a = build_recording(sc, tmp_path / "a")
    b = build_recording(sc, tmp_path / "b")
    assert np.array_equal(a.data, b.data)


def test_meta_validates(recordings):
    rec, _ = recordings("car_nicobar_m7")
    meta = RecordingMeta.model_validate_json((rec.path / "meta.json").read_text())
    assert meta.truth[-1].cls == "earthquake"
    assert rec.data.shape == (12000, 1000)


def test_channel_500_sits_at_car_nicobar(recordings):
    rec, _ = recordings("car_nicobar_m7")
    lat, lon = channel_positions(rec.meta)
    cn = city("Car Nicobar")
    assert haversine_km(lat[500], lon[500], cn.lat, cn.lon) < 1.0


def test_epicentre_is_about_22_km_from_the_cable():
    path = CablePath.load("cani_car_nicobar")
    lat, lon = path.point_at(np.linspace(0, path.length_km, 3000))
    assert 20.0 < haversine_km(8.7, 92.9, lat, lon).min() < 24.0


def test_quake_energy_jumps_at_true_p(recordings):
    rec, sc = recordings("car_nicobar_m7")
    quake = sc.events[-1]
    tp, _ = quake.arrivals(make_context(sc))
    live = np.abs(np.asarray(rec.data[:100])).max(axis=0) > 0
    ch = int(np.argmin(np.where(live, tp, np.inf)))
    sos = butter(4, [1.0, 10.0], btype="band", fs=100, output="sos")
    x = sosfilt(sos, np.asarray(rec.data[:, ch], dtype=float))  # causal: nothing before the onset
    noise = np.abs(x[:1000]).max()
    first_loud = np.argmax(np.abs(x) > 5 * noise) / 100.0
    assert abs(first_loud - tp[ch]) < 0.2


def test_plan_example_alert_validates():
    example = {
        "id": "evt-0007", "rev": 2, "status": "updated", "mode": "scenario",
        "source": "car_nicobar_m7", "class": "earthquake", "confidence": 0.93,
        "classifier": "resnet", "detected_at_s": 15.5, "origin_time_s": 10.1,
        "gate": {"coverage": 0.82, "apparent_velocity_kms": 7.4, "channels": [112, 934]},
        "picks": {"p_s": 14.7, "s_s": 18.7, "method": "stalta"},
        "location": {"along_cable_km": 61.2, "distance_km": 30.0, "lat": 8.7, "lon": 92.9,
                     "ambiguous": True, "alt": {"lat": 8.8, "lon": 93.3}},
        "magnitude": {"value": 6.8, "quality": "rough"},
        "warnings": [{"city": "Port Blair", "distance_km": 325, "s_arrival_s": 103.0,
                      "land_station_alert_s": 62.1}],
        "latency_ms": 840,
    }
    alert = Alert.model_validate(example)
    assert alert.to_json()["class"] == "earthquake"
    assert json.loads(json.dumps(alert.to_json()))["type"] == "alert"
