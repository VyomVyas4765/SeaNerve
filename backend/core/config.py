"""Every constant in one place: paths, wave speeds, amplitude law, detection thresholds."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

REPO_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_DIR / "data"
RECORDINGS_DIR = DATA_DIR / "recordings"
GEO_DIR = DATA_DIR / "geo"
PLOTS_DIR = DATA_DIR / "plots"

load_dotenv(REPO_DIR / ".env")
PROFILE = os.getenv("SEANERVE_PROFILE", "demo")  # "demo" shortens the cable-protection waits

FS_HZ = 100

# --- Wave speeds -----------------------------------------------------------------------------
# Crustal speeds near the source; faster deep-path speeds beyond FAR_KM, so far cities such as
# Chennai don't get an overstated warning.
VP_KMS = 6.5
VS_KMS = 3.5
VP_FAR_KMS = 8.0
VS_FAR_KMS = 4.6
FAR_KM = 200.0


def travel_time(r_km, phase: str, vp: float = VP_KMS, vs: float = VS_KMS):
    """Seconds for a P or S wave to cover r_km. Used by the generator and the locator alike."""
    near, far = (vp, VP_FAR_KMS) if phase == "P" else (vs, VS_FAR_KMS)
    r = np.asarray(r_km, dtype=float)
    t = np.where(r <= FAR_KM, r / near, FAR_KM / near + (r - FAR_KM) / far)
    return t if t.ndim else float(t)


# --- Amplitude law ---------------------------------------------------------------------------
# log10(A) = a*M + b*log10(r_km) + c, with A the peak S amplitude in units of the noise level.
# Starting values: an M3 at 50 km is about 5x noise. Real data shifts c (see magnitude.py).
AMP_A = 1.0
AMP_B = -1.6
AMP_C = 0.4
P_TO_S_RATIO = 0.25

# --- Cleaning --------------------------------------------------------------------------------
QUAKE_BAND_HZ = (1.0, 10.0)
LOCAL_BAND_HZ = (5.0, 45.0)
DISPLAY_BAND_HZ = (1.0, 45.0)
FILTER_ORDER = 4
NOISE_TAU_S = 30.0
MASK_NOISY_FACTOR = 5.0  # mask channels noisier than this times the median
COMMON_MODE_MIN_QUIET = 0.2  # skip common-mode removal when fewer channels than this are quiet

# --- Trigger (STA/LTA) -----------------------------------------------------------------------
STA_S = 0.5
LTA_S = 10.0
TRIGGER_ON = 4.0
TRIGGER_OFF = 1.5
WARMUP_S = 10.0  # no triggers until the long average has seen this much data
ONSET_DELAY_S = 0.025  # filter + STA lag, subtracted from each onset; measured on car_nicobar_m7

# --- Physics gate ----------------------------------------------------------------------------
GATE_WINDOW_S = 15.0
GATE_MIN_CHANNELS = 10
GATE_SMOOTH_CHANNELS = 15
GATE_MIN_COVERAGE = 0.30
GATE_MIN_SPAN_KM = 5.0  # or half the array, whichever is smaller
GATE_MIN_SPEED_KMS = 1.0
GATE_FIT_TOL_S = 0.25
GATE_MIN_INLIERS = 0.60
GATE_GRID_COARSE_KM = 10.0
GATE_GRID_FINE_KM = 2.0
GATE_GRID_MARGIN_KM = 150.0
GATE_DEPTHS_KM = (5.0, 10.0, 20.0, 30.0, 40.0)
NOMINAL_DEPTH_KM = 20.0  # typical depth on the Andaman-Sumatra interface
GATE_DEPTH_PENALTY_S_PER_KM = 0.002
GATE_MAX_FIT_CHANNELS = 120
GATE_REFINE_CANDIDATES = 5
GATE_WARM_START_S = 5.0  # reuse the last good epicentre as the starting point for this long
TRENCH_SIDE = "west"  # preferred epicentre when the two sides of the cable fit equally well

# --- Picks, location, warnings ---------------------------------------------------------------
S_STACK_CHANNELS = 50
S_STA_S = 0.5
S_LTA_S = 5.0
S_TRIGGER_ON = 3.0
S_ONSET_DELAY_S = 0.2  # STA lag on the stacked envelope; measured on car_nicobar_m7
LAND_STATION_PROCESSING_S = 2.0  # a seismometer in the city alerts at P arrival plus this
EVENT_FINAL_AFTER_S = 60.0  # an alert becomes final this long after P
REARM_TRIGGERED_FRACTION = 0.05  # a new event can start once fewer channels than this are busy
