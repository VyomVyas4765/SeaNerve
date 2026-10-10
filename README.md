# SeaNerve

Turning undersea internet cables into an earthquake early-warning network, starting with India's
2,300 km Chennai–Andaman (CANI) cable.

When an earthquake shakes the seabed, it stretches a fibre-optic cable lying on it by a few
nanometres, and that slightly changes the laser light travelling inside. A technique called
**DAS** (distributed acoustic sensing) reads those changes every few metres along the cable, so one
cable acts like thousands of seismometers sitting right next to the fault. SeaNerve is the software
that reads such recordings, decides whether something is a real earthquake, works out where it is,
and counts down the seconds until the shaking reaches each coastal city. The same fibre also notices
ships and dragged anchors, so the cable can warn about threats to itself.

This repository is the **software track** for Hackoverflow 10.0: a Python pipeline, a FastAPI server
and a React dashboard. The desk-scale fibre hardware rigs are out of scope.

## How it works

```
recording ──► clean ──► trigger ──► physics gate ──► pick P & S ──► locate ──► warn ──► dashboard
(real or       remove     "this       "did it sweep     first wave     how far   seconds
 simulated)    noise      channel     along the cable   and second     away      until S waves
                          got loud"   like a quake?"    wave arrive               hit each city
```

1. **Recording.** A grid of numbers: time down, position along the cable across. Real recordings come
   from the QuakeFlow DAS dataset; simulated ones come from our own generator, which also writes down
   the right answer so tests can check the pipeline.
2. **Clean.** Remove noise that hits the whole cable at once and keep the frequency bands where quakes
   (1–10 Hz) and ships or anchors (5–45 Hz) live.
3. **Trigger (STA/LTA).** For each channel, compare the last half-second of energy with the last ten
   seconds. A sudden jump marks the moment that channel "heard" something.
4. **Physics gate.** A real quake reaches channels one after another at seismic speed (kilometres per
   second), drawing a curved line across the waterfall. A ship or a bump lights up only a few
   neighbouring channels. Only the curved line passes, which is how false alarms are kept out, and
   judges can see the line.
5. **Pick, locate, warn.** Earthquakes send a fast P wave and a slower, more damaging S wave. The gap
   between them gives the distance (about 7.6 km per second of gap). From the distance and the
   wave speed we predict when the S wave reaches each city and show a countdown.
6. **Classify (second opinion).** A small image classifier looks at the event as a picture and labels
   it earthquake, vessel, anchor, ocean or noise. Simple rules are the offline fallback.
7. **Cable protection.** Small local events the gate rejects are tracked along the cable. A slow,
   loud, impulsive one (an anchor being dragged) raises a cable-threat alarm.

Everything reaches the browser over one WebSocket. The dashboard only draws what arrives.

### Two modes, one pipeline

| Mode | Plays | Shows |
|---|---|---|
| **Replay** | A real earthquake recorded on fibre (QuakeFlow DAS) | The pipeline works on real data, with the USGS catalog values beside ours |
| **Scenario** | A simulated M7.0 quake near Car Nicobar on the CANI route | Why it matters for India: rings spreading on the map and countdowns for Port Blair and other cities |

Scenario data is simulated and labelled **SIMULATED** on screen at all times.

## Repository layout

```
backend/
  core/          signal code, no web imports (runs from a terminal and from tests)
    synth/       synthetic generator and named scenarios
    pipeline/    clean, trigger, gate, pick, locate, magnitude, warning, tracker, classify, engine
  server/        FastAPI app, replay loop, message schemas
  tools/         one-off scripts: make scenarios, export patches, convert QuakeFlow files, evaluate
  tests/         pytest
frontend/        Vite + React + TypeScript dashboard (Leaflet map, canvas waterfall, Zustand store)
data/
  geo/           cable route, coastline, cities (small, committed)
  recordings/    data.npy + meta.json per recording (large, gitignored)
```

## Setup

Requires Python 3.11+ and Node 20+. Commands below are for PowerShell on Windows.

```powershell
# Backend
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pytest

# Frontend
cd ..\frontend
npm install
```

Copy `.env.example` to `.env` and add a Roboflow key if you want the hosted classifier. Without it,
the rules classifier is used.

## Run

First time only, write the simulated recordings (about 400 MB in `data/recordings/`):

```powershell
cd backend
.venv\Scripts\python tools\make_scenarios.py
```

**Demo (one process, one port, works with Wi-Fi off):**

```powershell
cd frontend
npm run build
cd ..\backend
.venv\Scripts\python -m uvicorn server.main:app --port 8000
```

Open http://localhost:8000 and click a demo moment: **1 Real quake**, **2 India M7** or
**3 Anchor drag** (each starts at its demo speed). Keys: `1` `2` `3` start a moment, `Space` pauses or
resumes, `R` restarts. Every other recording is under *All recordings*. Hover the waterfall to read
the distance and time under the pointer. The layout is checked at 1920×1080 and 1366×768.

**Development (hot reload):** run the same uvicorn command with `--reload`, and in a second terminal
`npm run dev` in `frontend/`, then open http://localhost:5173. Vite forwards `/api`, `/ws` and `/geo`
to port 8000.

## Status

Agreed scope: [docs/build-spec.md](docs/build-spec.md).

Done (plan hours 0-17, Checkpoints A and B):

- Data contracts (`backend/core/contracts.py`, mirrored in `frontend/src/types.ts`).
- Synthetic generator and the named recordings: `car_nicobar_m7`, `vessel_crossing`, `anchor_drag`,
  `quiet`, `random-<seed>`.
- Clean, STA/LTA trigger and physics gate. The gate passes the simulated M7 at 17 s (P reaches the
  cable at 14.6 s) with the epicentre within about 1 km, and never passes the ship, the anchor or
  10 minutes of quiet sea.
- Stream engine: S pick, distance, origin time, rough magnitude and city countdowns, with alerts
  revised from preliminary to updated to final. On the M7: distance 30 km (true 29.7), origin
  within 0.1 s, M 6.9 (true 7.0), Port Blair's S arrival within 0.1 s.
- FastAPI replay server (`/api/...`, `/ws`) and the dashboard: waterfall with the gate's curve and
  P and S marks, offline map with spreading rings and countdowns, alert card, cable-versus-seismometer
  bar (Port Blair: about 77 s against 36 s), pipeline strip, event log and metrics.

Tools:

```powershell
cd backend
.venv\Scripts\python tools\plot_recording.py          # waterfall PNGs in data/plots/
.venv\Scripts\python tools\run_gate.py car_nicobar_m7  # the gate's verdict, second by second
```

Next: real QuakeFlow recordings in Replay mode (plan hours 16-18), then the ship and anchor tracker.
