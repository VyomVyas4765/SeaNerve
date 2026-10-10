# What we're building

This is the agreed scope for the SeaNerve software track. It starts from the software implementation
plan (`SeaNerve software plan.pdf`, 2026-10-10) and records every place we do something different,
with the reason. Where this file says nothing, the plan's numbers and formats stand.

Rule used for every choice: **the easiest version that still works on stage.**

## In one paragraph

One web app that runs on a laptop with Wi-Fi off. It has two modes. **Scenario** plays made-up
recordings of India's Chennai–Andaman cable: a big quake near Car Nicobar, and a ship dragging its
anchor over the cable. **Replay** plays a real earthquake recorded on real fibre in California,
ideally the Monterey Bay seafloor cable, and puts our numbers beside the official USGS ones. Behind
both is the same engine: clean the signal, spot sudden loudness, check it sweeps along the cable like
a quake, time the P and S waves, work out where and how big, and count down to each city.

## What the judges see (3 minutes)

| Time | Mode and recording | On screen |
|---|---|---|
| 0:00 | Dashboard paused on the India map | The cable beside the fault; the problem |
| 0:20 | Replay: a real quake, 2× speed | A line sweeps the waterfall, the gate curve snaps on, the alert shows our origin time and rough magnitude next to USGS |
| 1:10 | Scenario: `car_nicobar_m7` | Rings spread from the epicentre; countdowns for Car Nicobar, Kamorta, Port Blair and Chennai; a bar shows about 77 s of warning for Port Blair from the cable against about 36 s from a seismometer in Port Blair |
| 2:00 | Scenario: `anchor_drag`, 5× speed | A narrow streak on the waterfall, a red marker on the map, a cable-threat alarm |
| 2:30 | Metrics panel | Latency, detection rate, false alarms, share of data kept |

## What's in

**Recordings**

| Id | Kind | Geometry | Used for |
|---|---|---|---|
| `car_nicobar_m7` | Simulated | 200 km of cable centred on Car Nicobar, 200 m spacing, 1,000 channels | The India demo |
| `vessel_crossing` | Simulated | 10 km of cable near Car Nicobar, 10 m spacing, 1,000 channels | Gate rejects it; tracker shows Info |
| `anchor_drag` | Simulated | Same 10 km, 10 m spacing | Cable-threat alarm |
| `quiet` | Simulated | Same as `car_nicobar_m7` | False alarms per hour |
| `random(seed)` | Simulated | Either geometry | Classifier training and evaluation |
| 3–5 QuakeFlow events | Real | Native array (unknown positions) | Replay mode; at least one from Monterey Bay if available |

**Engine stages:** clean → trigger (STA/LTA) → physics gate → P and S picks → locate → rough
magnitude → city countdowns, plus the ship and anchor tracker for small local events.

**Classifier:** rules first; a small ResNet-18 trained on the laptop's CPU replaces their answer when
its file is present. Classes: `earthquake`, `vessel`, `anchor`, `noise`.

**Server and dashboard:** as in the plan (routes, WebSocket messages, waterfall, map, alert card,
pipeline strip, event log, metrics, CAP download).

## Changes from the plan

| # | Plan says | We do | Why |
|---|---|---|---|
| 1 | Roboflow classifier with cache, local server and rules fallback | ResNet-18 in PyTorch, trained and run on the laptop; rules as fallback | Matches the deck, needs no account, credits or network on stage, and drops the cache/fallback chain |
| 2 | Five classes including `ocean` | Four classes; swell stays in recordings as background | No detector listens below 1 Hz, so an ocean event could never fire |
| 3 | Gate fits a straight-cable curve with `least_squares` | Scenario cables: try every point on a map grid (10 km, then 2 km, then 0.5 km steps, great-circle distances) with the real channel positions and keep the one that best explains the arrival times; compare the best fit on each side of the cable and prefer the trench (west) side when they tie. Real arrays: a smooth curve along the cable | Handles the 24° bend at Car Nicobar, gives the epicentre on the map directly, and is easy to explain |
| 4 | Epicentre placed at the S–P distance from the cable | Comes out of the grid search, trying depths of 5–40 km with a gentle preference for 20 km | The S–P gap measures distance to the underground source, not to the map point; with only a few channels triggered, depth and distance trade off |
| 5 | Ships and anchors on the 200 m-spaced India cable | Their own 10 km recordings at 10 m spacing; ships move at an angle to the cable | At 200 m spacing an anchor moves less than one channel in a minute and its speed can't be measured |
| 6 | Classifier answer in the first alert | Alert goes out on the gate alone; the classifier label arrives as an update about 20 s later and can cancel it | The classifier needs a 20 s picture, so its answer can't exist at detection time |
| 7 | One distance for magnitude | Magnitude per channel from its own distance, then the median | Triggered channels range from about 30 to 150 km away |
| 8 | No warm-up rule | Prime the averages from the first second; no triggers in the first 10 s | Real files start only about 20 s before the quake |
| 9 | Common-noise removal always on | On or off per recording (`meta.json`); when on, estimated only from channels not currently triggered | On short land arrays a nearby quake looks like shared noise and gets removed; during the simulated M7 the "shared noise" became the quake and made far channels trigger early |
| 10 | Stream clock stops when the data ends | Clock keeps running | Chennai's S waves arrive about 7 minutes after the quake starts |
| 11 | Speeds 1, 2, 5, 10× | 1, 2, 5× | At 10× each second must be processed in 100 ms |
| 12 | One wave speed for every city | 6.5 / 3.5 km/s up to 200 km, 8.0 / 4.6 km/s beyond | One speed overstates Chennai's warning by about 1.5 minutes |
| 13 | "A few channels 5× noisier" with a "more than 5×" mask | 8× noisier | The plan's values sit exactly on the cut-off |
| 14 | Waterfall signal not specified; cells clipped at ±4; newest row on top | Noise-normalised 1–45 Hz on a signed log scale, light background, newest row at the bottom | Quakes and ships both show; noise stays a faint speckle while an M7 still shows its wave trains instead of a solid block; matches the deck mockup, where the quake's curve points up |
| 15 | Patch band 0.1–45 Hz, not produced by the cleaning step | One shared function draws patches from the raw buffer, for training and live | Same picture in both places |
| 16 | CAP updates | Include `references` to the first alert | CAP 1.2 requires it for `Update` |
| 17 | All of `data/` gitignored | `data/geo/` committed; recordings ignored | The cable route and city list are small and hand-made |

## Not building

- The desk fibre rigs and the Live rig mode (hardware track).
- Roboflow. Swap it back only if the hackathon has a Roboflow prize.
- An ocean class or "ocean monitoring" claim.
- PhaseNet-DAS. If everything else is done, run it offline on the Replay files and show its picks
  beside ours.
- Magnitude fitted on 20+ events, the multi-event picker, and the `quake_plus_vessel` scenario.
- Tsunami prediction. The pitch already says tsunami detection from cables is the next research step.

## Build order

| Hours | Block | Checkpoint |
|---|---|---|
| 0–1 | Data contracts as Pydantic models and TypeScript types; start QuakeFlow downloads | |
| 1–3 | Generator, the named recordings, quick waterfall plots | Recordings look right by eye |
| 3–6 | Clean, trigger, physics gate, with tests | **A:** gate passes the quake, rejects the ship and anchor |
| 6–8 | Picks, locate, magnitude, countdowns | Distance within 10 %, origin time within 1 s |
| 8–10 | Engine, replay server, WebSocket, routes | Messages visible in a WebSocket client |
| 10–14 | Dashboard: socket and store, waterfall, map and rings, alert card and log | **B:** India scenario runs end to end in the browser |
| 14–16 | Pipeline strip, gate overlay, countdowns, cable-versus-seismometer bar, polish | India demo presentable |
| 16–18 | Real data: convert files, tune, USGS column | **C:** Replay catches a real quake |
| 18–19.5 | Ship and anchor tracker, threat levels, map markers | Anchor scenario raises the alarm |
| 19.5–21 | Classifier: export patches, train ResNet-18 on CPU, wire in with rules fallback | Label on the alert card |
| 21–22 | `evaluate.py`, metrics panel, CAP download | Numbers for the pitch |
| 22–24 | Rehearse three times, record a backup video, fix what breaks | A demo already run |

If behind, cut in this order: CAP download, then the metrics panel, then ResNet-18 (keep the rules).
Never cut the rehearsal.

## Deck edits before the final pitch

`SeaNerve_ppt.pptx` promises things this build doesn't do:

- **Slide 2, Key features:** "ResNet-18 labels earthquake, vessel, ocean or noise" → "earthquake,
  vessel, anchor or noise". "PhaseNet-DAS picks the P and S arrivals" → "picks the P and S arrivals".
- **Slide 3, Technical approach:** "Python / SciPy / ObsPy" → "Python / SciPy". "DASCore / h5py" →
  "h5py". Drop the PhaseNet-DAS row or mark it "next". Data table: keep QuakeFlow DAS; mark OOI,
  PoroTomo and Global DAS Month as "next", and add "Simulated India scenarios (labelled)".
- **Pitch close:** "earthquake warning, ocean monitoring and guarding itself against anchors" →
  "earthquake warning and guarding itself against anchors".
