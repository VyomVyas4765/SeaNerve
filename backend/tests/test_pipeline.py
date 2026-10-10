import time

import numpy as np
import pytest
from scipy.signal import sosfilt

from core.contracts import Trigger
from core.geo import haversine_km
from core.pipeline.detector import Detector, blocks
from core.pipeline.preprocess import Preprocessor
from core.synth.generator import make_context


def run(rec):
    """Feed a recording in 1 s blocks; return the detector and every gate verdict."""
    det = Detector(rec.meta)
    verdicts = [step.trigger for block in blocks(rec) if (step := det.feed(block)).trigger]
    return det, verdicts


def test_streaming_filters_match_whole_array():
    rng = np.random.default_rng(0)
    x = rng.standard_normal((1000, 20))
    pre = Preprocessor(20, fs=100, remove_common_mode=True)
    streamed = np.concatenate([pre.process(x[i:i + 100]).filtered["quake"] for i in range(0, 1000, 100)])
    whole = sosfilt(pre.sos["quake"], x - np.median(x, axis=1, keepdims=True), axis=0)
    assert np.allclose(streamed, whole)


def test_trigger_onsets_match_true_p(recordings):
    rec, sc = recordings("car_nicobar_m7")
    tp, _ = sc.events[-1].arrivals(make_context(sc))
    det = Detector(rec.meta)
    onset = np.full(rec.meta.n_channels, np.nan)  # each channel's first trigger
    for block in blocks(rec):
        det.feed(block)
        first = np.isnan(onset) & np.isfinite(det.stalta.onset)
        onset[first] = det.stalta.onset[first]
    ok = det.pre.usable & np.isfinite(onset)
    assert ok.sum() > 0.9 * det.pre.usable.sum()
    assert np.mean(np.abs(onset[ok] - tp[ok]) < 0.3) > 0.95


def test_gate_passes_the_quake_and_finds_it(recordings):
    rec, _ = recordings("car_nicobar_m7")
    quake = rec.meta.truth[-1]
    _, verdicts = run(rec)
    passed = [v for v in verdicts if v.passed]
    assert passed, "the gate never passed the M7"
    assert passed[0].t_s <= 18.0  # P reaches the cable at 14.6 s
    assert max(v.coverage for v in passed) > 0.6
    errors = [haversine_km(v.epicentre.lat, v.epicentre.lon, quake.lat, quake.lon) for v in passed]
    assert np.median(errors) < 5.0
    assert errors[0] < 10.0
    for v in verdicts:  # every message is a valid contract
        Trigger.model_validate(v.to_json())


@pytest.mark.parametrize("scenario_id", ["vessel_crossing", "anchor_drag", "quiet"])
def test_gate_never_passes_ships_anchors_or_quiet_sea(recordings, scenario_id):
    rec, _ = recordings(scenario_id)
    _, verdicts = run(rec)
    assert not any(v.passed for v in verdicts)


def test_one_second_of_1000_channels_is_fast(recordings):
    rec, _ = recordings("car_nicobar_m7")
    det = Detector(rec.meta)
    times = []
    for block in blocks(rec):
        start = time.perf_counter()
        det.feed(block)
        times.append(time.perf_counter() - start)
    assert np.median(times) < 0.1
