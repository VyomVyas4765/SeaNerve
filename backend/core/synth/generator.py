"""build_recording(scenario) -> Recording: noise first, then every event, written chunk by chunk."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from core import config
from core.contracts import CableRef, RecordingMeta, Velocity
from core.geo import CablePath
from core.recording import Recording, open_recording, write_meta
from core.synth.events import Context, Noise
from core.synth.scenarios import Scenario

CHUNK_S = 10.0


def make_context(scenario: Scenario) -> Context:
    g = scenario.geometry
    x_km = g.channel0_km + np.arange(g.n_channels) * g.dx_m / 1000.0
    lat, lon = CablePath.load(g.path).point_at(x_km)
    return Context(float(config.FS_HZ), x_km, lat, lon, g.shore_km)


def build_recording(scenario: Scenario, out_dir: str | Path) -> Recording:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    g = scenario.geometry
    fs = config.FS_HZ
    n_ch = g.n_channels
    n_samples = int(round(scenario.duration_s * fs))
    ctx = make_context(scenario)

    # Separate random streams, so adding an event never changes the noise.
    rng_layout, rng_noise, rng_events = (np.random.default_rng(s)
                                         for s in np.random.SeedSequence(scenario.seed).spawn(3))
    coupling = rng_layout.uniform(0.5, 1.5, n_ch).astype(np.float32)  # real cables couple unevenly
    order = rng_layout.permutation(n_ch)
    n_noisy = int(round(scenario.noisy_fraction * n_ch))
    n_dead = int(round(scenario.dead_fraction * n_ch))
    noisy, dead = order[:n_noisy], order[n_noisy:n_noisy + n_dead]

    noise = Noise(n_ch, rng_noise, noisy)
    renderers = [ev.bind(ctx, rng_events) for ev in scenario.events]

    data = np.lib.format.open_memmap(out_dir / "data.npy", mode="w+", dtype=np.float32,
                                     shape=(n_samples, n_ch))
    chunk = int(CHUNK_S * fs)
    for i0 in range(0, n_samples, chunk):
        i1 = min(i0 + chunk, n_samples)
        t = np.arange(i0, i1) / fs
        signal = np.zeros((i1 - i0, n_ch), dtype=np.float32)
        for render in renderers:
            signal += render(t)
        block = noise.render(i1 - i0) + signal * coupling
        block[:, dead] = 0.0
        data[i0:i1] = block
    data.flush()
    del data

    meta = RecordingMeta(
        id=scenario.id,
        title=scenario.title,
        kind="synthetic",
        fs_hz=fs,
        dx_m=g.dx_m,
        n_channels=n_ch,
        n_samples=n_samples,
        start_time=scenario.start_time,
        cable=CableRef(path=g.path, channel0_km=round(g.channel0_km, 4)),
        velocity=Velocity(vp_kms=config.VP_KMS, vs_kms=config.VS_KMS),
        remove_common_mode=scenario.remove_common_mode,
        seed=scenario.seed,
        truth=[ev.truth(ctx) for ev in scenario.events],
    )
    write_meta(out_dir, meta)
    return open_recording(out_dir)
