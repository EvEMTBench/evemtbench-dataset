"""
Check for a growing DC component in the recorded currents. Unstable fits of frequency-dependent cable and line models
can cause such a drift: it is too slow for a cycle-to-cycle comparison of the samples but can grow to more than 1 kA
within the exported window. The same check is applied to
- every generated multi_grid topology at the end of its 1 s initialisation run (setting_generation/
  generate_dynamic_grid_settings.py, check_grid_consistency), and
- every simulation in the last full cycle before the event (util/post_processing.py, check_result_file).
"""
import numpy as np

MIN_DC_A = 0.1  # a DC component is only flagged above this absolute value (nearly zero currents, e.g. neutral-point
#                 currents, are therefore never flagged on numerical noise) ...
MAX_DC_SHARE = 0.01  # ... and above this share of the AC amplitude


def growing_dc(previous_cycle, last_cycle):
    """
    previous_cycle, last_cycle: two consecutive full cycles (samples x currents).
    A current is flagged if, in the last cycle, its DC component (absolute mean) is above MIN_DC_A, above MAX_DC_SHARE
    of its AC amplitude (half peak-to-peak) and larger than in the previous cycle (a decaying DC component is accepted).
    Returns (flagged, dc, dc_previous, ac) with one value per current.
    """
    previous_cycle = np.asarray(previous_cycle, dtype=float)
    last_cycle = np.asarray(last_cycle, dtype=float)
    ac = (last_cycle.max(axis=0) - last_cycle.min(axis=0)) / 2
    dc = np.abs(last_cycle.mean(axis=0))
    dc_previous = np.abs(previous_cycle.mean(axis=0))
    flagged = (dc > MIN_DC_A) & (dc > MAX_DC_SHARE * ac) & (dc > dc_previous)
    return flagged, dc, dc_previous, ac
