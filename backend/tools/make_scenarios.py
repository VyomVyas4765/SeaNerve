"""Write the named synthetic recordings to data/recordings/<id>/.

    python tools/make_scenarios.py                 # all named recordings
    python tools/make_scenarios.py anchor_drag random-3
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import RECORDINGS_DIR  # noqa: E402
from core.synth import scenarios  # noqa: E402
from core.synth.generator import build_recording  # noqa: E402


def main(ids: list[str]) -> None:
    for scenario_id in ids or list(scenarios.NAMED):
        start = time.perf_counter()
        rec = build_recording(scenarios.get(scenario_id), RECORDINGS_DIR / scenario_id)
        m = rec.meta
        print(f"{m.id:18s} {m.duration_s:5.0f} s x {m.n_channels} channels at {m.dx_m:g} m "
              f"({rec.data.nbytes / 1e6:.0f} MB) in {time.perf_counter() - start:.1f} s")


if __name__ == "__main__":
    main(sys.argv[1:])
