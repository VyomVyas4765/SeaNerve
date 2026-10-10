"""Checkpoint A in the terminal: feed a recording through clean -> trigger -> gate in 1 s blocks.

    python tools/run_gate.py car_nicobar_m7 vessel_crossing anchor_drag quiet
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from core.config import RECORDINGS_DIR  # noqa: E402
from core.geo import haversine_km  # noqa: E402
from core.pipeline.detector import Detector, blocks  # noqa: E402
from core.recording import open_recording  # noqa: E402


def run(recording_id: str, verbose: bool = True) -> None:
    rec = open_recording(RECORDINGS_DIR / recording_id)
    det = Detector(rec.meta)
    quake = next((e for e in rec.meta.truth if e.cls == "earthquake"), None)
    timings, passes = [], []
    print(f"\n=== {recording_id}: {rec.meta.title}")
    for block in blocks(rec):
        start = time.perf_counter()
        step = det.feed(block)
        timings.append((time.perf_counter() - start) * 1000)
        trig = step.trigger
        if trig is None:
            continue
        if trig.passed:
            passes.append(trig)
        if verbose:
            where = ""
            if trig.epicentre:
                where = f" epi {trig.epicentre.lat:.2f},{trig.epicentre.lon:.2f} z{trig.epicentre.depth_km:g}"
                if quake:
                    err = haversine_km(trig.epicentre.lat, trig.epicentre.lon, quake.lat, quake.lon)
                    where += f" (off {err:.1f} km)"
            print(f"t={trig.t_s:6.1f}s {'PASS' if trig.passed else 'fail'} "
                  f"cov {trig.coverage:.2f} span {trig.span_km:6.1f} km "
                  f"v {trig.apparent_velocity_kms:6.1f} km/s fit {trig.inlier_fraction:.0%}"
                  f"{where}  [{trig.reason}]")
    t = np.array(timings)
    verdict = f"PASS first at {passes[0].t_s:.1f} s" if passes else "never passed"
    print(f"--> {verdict}; per 1 s block: mean {t.mean():.0f} ms, max {t.max():.0f} ms")


if __name__ == "__main__":
    for rid in sys.argv[1:] or ["car_nicobar_m7", "vessel_crossing", "anchor_drag"]:
        run(rid)
