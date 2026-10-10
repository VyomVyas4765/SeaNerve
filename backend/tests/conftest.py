"""Synthetic recordings built once per test session (they take a second or two each)."""

import pytest

from core.synth import scenarios
from core.synth.generator import build_recording


@pytest.fixture(scope="session")
def recordings(tmp_path_factory):
    root = tmp_path_factory.mktemp("recordings")
    cache = {}

    def get(scenario_id: str):
        if scenario_id not in cache:
            sc = scenarios.quiet(duration_s=120.0) if scenario_id == "quiet" else scenarios.get(scenario_id)
            cache[scenario_id] = (build_recording(sc, root / scenario_id), sc)
        return cache[scenario_id]

    return get
