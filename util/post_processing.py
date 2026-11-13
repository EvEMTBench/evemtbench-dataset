import argparse
import glob
import os
import shutil
import pandas as pd
import numpy as np
from tqdm import tqdm

from util.dc_check import growing_dc

# Configuration
CYCLES = 2  # 40ms
VOLTAGE_LIMITS = (0.9, 1.1)  # pu, RMS of the first CYCLES cycles of the exported window
MAX_PEAK_PU = 5.0  # pu of the nominal phase-to-ground peak, applied to the whole exported window
MAX_PRE_EVENT_CHANGE_PU = 0.005  # pu of the nominal phase-to-ground peak, voltage change from cycle to cycle before the event


def get_pre_event_dc(data, variables, fs, fn, event_start):
    """
    Growing-DC check (util/dc_check.py, the same check as for the generated topologies) of the currents in the last full
    cycle before the event, compared with the cycle before it. Returns (flagged, DC component) per current. Empty if the
    exported window does not start in steady state (debug mode) or the event is too early for two full cycles.
    """
    period = int(round(fs / fn))
    n_event = int(round((event_start - data[0, 0]) * fs)) if np.isfinite(event_start) else 0
    if data[0, 0] < 0.5 or n_event < 2 * period:
        return np.array([], dtype=bool), np.array([])
    current_cols = [i for i, var in enumerate(variables) if 'Isec' in var]
    flagged, dc, _, _ = growing_dc(data[n_event - 2 * period:n_event - period, current_cols], data[n_event - period:n_event, current_cols])
    return flagged, dc


def get_pre_event_change(data, voltage_cols, fs, fn, event_start, base_voltage_ln):
    """
    Steady-state check before the event: largest difference between the voltage samples of the last full cycle before
    the event and the samples one cycle earlier, in pu of the nominal phase-to-ground peak (0 for a periodic signal).
    NaN in the cases in which get_pre_event_dc returns nothing.
    """
    period = int(round(fs / fn))
    n_event = int(round((event_start - data[0, 0]) * fs)) if np.isfinite(event_start) else 0
    if data[0, 0] < 0.5 or n_event < 2 * period:
        return np.nan
    last_cycle = data[n_event - period:n_event, voltage_cols]
    previous_cycle = data[n_event - 2 * period:n_event - period, voltage_cols]
    return float(np.abs(last_cycle - previous_cycle).max() / (base_voltage_ln * np.sqrt(2)))


def check_result_file(csv_file, vn, fn, event_start=np.nan):
    """
    Checks one result file and removes it if it is not plausible:
    - non_finite: any value is NaN or infinite
    - pre_event_voltage: RMS voltage of the first CYCLES cycles outside VOLTAGE_LIMITS (operating state check)
    - pre_event_dc: in the last full cycle before the event, a current has a growing DC component above MIN_DC_A and
      above MAX_DC_SHARE of its AC amplitude (util/dc_check.py; numerical drift of frequency-dependent line models)
    - peak_amplitude: any voltage sample exceeds MAX_PEAK_PU (numerically unstable simulation)
    - pre_event_unsteady: in the last full cycle before the event, a voltage differs by more than MAX_PRE_EVENT_CHANGE_PU
      from its value one cycle earlier (grid not in steady state, e.g. a growing zero-sequence oscillation in a
      resonant-grounded grid)
    - unreadable: the file cannot be parsed as a numeric time series
    Returns a dict with the check results and the removal reason ('' if the file is kept).
    """
    base_voltage_ln = vn * 1000 / np.sqrt(3)  # Line-to-neutral base voltage (RMS)
    min_pu, max_pu = VOLTAGE_LIMITS

    result = {"pre_rms_min": np.nan, "pre_rms_max": np.nan, "pre_dc_max_A": np.nan, "max_peak_pu": np.nan,
              "finite": True, "removed_reason": ""}

    try:
        with open(csv_file) as f:
            f.readline()
            variables = f.readline().strip().split(',')
        data = pd.read_csv(csv_file, header=None, skiprows=2, dtype=np.float64, engine='c').values
        assert data.shape[0] > 1 and data.shape[1] == len(variables)
    except Exception as e:
        result["finite"] = False
        result["removed_reason"] = "unreadable"
        os.remove(csv_file)
        print(f'Not Ok (unreadable: {e!r}): {csv_file}')
        return result

    voltage_cols = [i for i, var in enumerate(variables) if 'Usec' in var and 'in V' in var]

    if not voltage_cols:
        print("found no voltage columns")
        return result

    result["finite"] = bool(np.isfinite(data).all())

    fs = 1 / (data[1, 0] - data[0, 0])
    n_samples = int(round(fs / fn * CYCLES))
    signals = data[:, voltage_cols]
    rms_pu = np.sqrt(np.mean(np.square(signals[:n_samples]), axis=0)) / base_voltage_ln
    result["pre_rms_min"] = float(np.min(rms_pu))
    result["pre_rms_max"] = float(np.max(rms_pu))
    result["max_peak_pu"] = float(np.max(np.abs(signals)) / (base_voltage_ln * np.sqrt(2)))
    dc_flagged, dc = get_pre_event_dc(data, variables, fs, fn, event_start)
    result["pre_dc_max_A"] = float(dc.max()) if dc.size else np.nan
    pre_event_dc = bool(dc_flagged.any())

    if not result["finite"]:
        result["removed_reason"] = "non_finite"
    elif not np.all((rms_pu >= min_pu) & (rms_pu <= max_pu)):
        result["removed_reason"] = "pre_event_voltage"
    elif pre_event_dc:
        result["removed_reason"] = "pre_event_dc"
    elif result["max_peak_pu"] > MAX_PEAK_PU:
        result["removed_reason"] = "peak_amplitude"
    elif get_pre_event_change(data, voltage_cols, fs, fn, event_start, base_voltage_ln) > MAX_PRE_EVENT_CHANGE_PU:
        result["removed_reason"] = "pre_event_unsteady"

    if result["removed_reason"]:
        os.remove(csv_file)
        print(f'Not Ok ({result["removed_reason"]}): {csv_file}')

    return result


def filter_failed_simulations(setting_file_path, sim_status):
    """
    Keeps the simulations that reported success (sim_status, from the status files of util/parallel_sim_handler.py) and
    have a result file. A simulation that ended without reporting success, e.g. because its process was terminated
    during the export, can leave an incomplete result file. Such a file is removed.
    """
    setting_df = pd.read_csv(setting_file_path)
    exists = setting_df['general/result_file_path'].apply(os.path.exists)
    if sim_status.empty and exists.any():
        raise FileNotFoundError(f"No status files in {os.path.join(os.path.dirname(setting_file_path), 'status')}: "
                                f"cannot tell which simulations succeeded, nothing was changed")
    succeeded = setting_df['general/sim_idx'].isin(sim_status.loc[sim_status['sim_status'] == 'success', 'sim_idx'])
    for result_path in setting_df.loc[exists & ~succeeded, 'general/result_file_path']:
        os.remove(result_path)
        print(f'Not Ok (no success reported): {result_path}')
    df_clean = setting_df[exists & succeeded]
    setting_file_path_clean = setting_file_path.replace('.csv', '_clean.csv')
    df_clean.to_csv(setting_file_path_clean, index=False)
    return setting_file_path_clean


def filter_voltage_violations(setting_file_path):
    """Filter out simulations with voltage violations or implausible waveforms. Returns the per-simulation checks."""
    setting_df = pd.read_csv(setting_file_path)

    # Extract grid name from path
    # Path format: .../dataset_type/grid_name/labels/settings.csv
    path_parts = setting_file_path.split(os.sep)
    grid_name = None
    for i, part in enumerate(path_parts):
        if part == 'labels' and i > 0:
            grid_name = path_parts[i-1]
            break

    check_columns = ["sim_idx", "pre_rms_min", "pre_rms_max", "pre_dc_max_A", "max_peak_pu", "finite", "removed_reason"]
    if not grid_name:
        print(f"  Could not determine grid name from {setting_file_path}")
        return pd.DataFrame(columns=check_columns)

    # Check each simulation
    checks = []
    for idx, row in tqdm(setting_df.iterrows()):
        check = check_result_file(row['general/result_file_path'], row['general/vn'], row['general/fn'],
                                  row.get('events/event_start', np.nan))
        check["sim_idx"] = int(row['general/sim_idx'])
        checks.append(check)
    checks = pd.DataFrame(checks, columns=check_columns)

    ok_mask = (checks["removed_reason"] == "").values
    print(f"  Filtered {(~ok_mask).sum()}/{len(ok_mask)} simulations "
          f"({checks['removed_reason'].value_counts().drop('', errors='ignore').to_dict()})")

    df_filtered = setting_df[ok_mask]
    df_filtered.to_csv(setting_file_path, index=False)
    return checks


def get_event_quota(shares, available, n_target):
    """
    Number of simulations per event type: proportional to shares (largest remainder rounding, ties by event name) and
    summing to exactly n_target. Event types with fewer available simulations than their quota keep all of them and the
    deficit is distributed among the other event types proportionally to their shares.
    """
    quota = pd.Series(0, index=shares.index)
    open_events = shares.index[available > 0]
    remaining = n_target
    while remaining > 0 and len(open_events) > 0:
        ideal = shares[open_events] / shares[open_events].sum() * remaining
        add = np.floor(ideal).astype(int)
        largest_remainders = (ideal - add).sort_values(ascending=False, kind='stable').index[:remaining - add.sum()]
        add[largest_remainders] += 1
        quota[open_events] += add
        excess = (quota - available).clip(lower=0)
        quota -= excess
        remaining = int(excess.sum())
        open_events = quota.index[quota < available]
    return quota


def select_target_number(setting_file_path, n_target, seed=0):
    """
    Reduces settings_clean.csv to exactly n_target simulations. The number of simulations per event type follows the
    event shares of all planned simulations (settings.csv), so failed and filtered simulations do not change the event
    distribution. Within each event type, simulations are drawn at random with a fixed seed, which keeps the
    distribution of all other parameters of the retained simulations and spreads the reduction over all topologies.
    Result files of unselected simulations are moved to <dataset>/data_unselected.
    Returns the sim_idx of the unselected simulations.
    """
    label_path = os.path.dirname(setting_file_path)
    clean_path = setting_file_path.replace('.csv', '_clean.csv')
    clean = pd.read_csv(clean_path)
    if len(clean) < n_target:
        print(f"  WARNING: only {len(clean)} simulations retained, {n_target} requested. Keeping all, simulate more.")
        return []

    planned_events = pd.read_csv(setting_file_path, usecols=['events/event_type'])['events/event_type']
    shares = planned_events.value_counts(normalize=True).sort_index()
    available = clean['events/event_type'].value_counts().reindex(shares.index, fill_value=0)
    quota = get_event_quota(shares, available, n_target)

    rng = np.random.default_rng(seed)
    selected = []
    for event, n in quota.items():
        candidates = clean.index[clean['events/event_type'] == event].to_numpy()
        selected.extend(rng.choice(candidates, size=int(n), replace=False))
    selected = np.sort(np.array(selected, dtype=int))
    unselected = clean.drop(index=selected)

    unselected_dir = os.path.join(os.path.dirname(label_path), 'data_unselected')
    os.makedirs(unselected_dir, exist_ok=True)
    for result_path in unselected['general/result_file_path']:
        shutil.move(result_path, os.path.join(unselected_dir, os.path.basename(result_path)))
    clean.loc[selected].to_csv(clean_path, index=False)

    summary = pd.DataFrame({'planned': planned_events.value_counts().reindex(shares.index), 'planned_share': shares,
                            'retained': available, 'target': (shares * n_target).round(1), 'selected': quota})
    summary.index.name = 'event_type'
    summary.to_csv(os.path.join(label_path, 'event_selection.csv'))
    short = summary[summary['selected'] < np.floor(summary['target'])]
    if len(short):
        print(f"  WARNING: not enough simulations for {short.index.tolist()}, event shares deviate:\n{short}")
    print(f"  Selected {len(selected)} of {len(clean)} simulations, moved {len(unselected)} result files to {unselected_dir}")
    return unselected['general/sim_idx'].astype(int).tolist()


def collect_sim_status(label_path):
    """Merges the per-simulation status files written by parallel_sim_handler.py."""
    status_files = glob.glob(os.path.join(label_path, 'status', 'sim_status_*.csv'))
    if not status_files:
        return pd.DataFrame(columns=["sim_idx", "sim_status", "sim_message"])
    return pd.concat([pd.read_csv(f) for f in status_files], ignore_index=True).drop_duplicates("sim_idx", keep="last")


def write_status_report(setting_file_path, sim_status, checks, unselected=()):
    """
    Writes labels/sim_status.csv with one row per planned simulation: outcome reported by the simulation
    (sim_status, unknown if it ended without reporting one), whether a result file of a successful simulation was
    written (result_written), the post-processing checks, the removal reason and whether the simulation is part of
    settings_clean.csv. missing_result: no result file, or the simulation did not report success.
    """
    label_path = os.path.dirname(setting_file_path)
    report_path = os.path.join(label_path, 'sim_status.csv')
    planned = pd.read_csv(setting_file_path, usecols=['general/sim_idx', 'general/result_file_path'])
    clean = pd.read_csv(setting_file_path.replace('.csv', '_clean.csv'), usecols=['general/sim_idx'])

    report = planned.rename(columns={'general/sim_idx': 'sim_idx'}).drop(columns='general/result_file_path')
    report = report.merge(sim_status, on='sim_idx', how='left')
    report = report.merge(checks, on='sim_idx', how='left')
    report['result_written'] = report['removed_reason'].notna()
    report['retained'] = report['sim_idx'].isin(clean['general/sim_idx'])
    report.loc[~report['result_written'], 'removed_reason'] = 'missing_result'
    report.loc[report['sim_idx'].isin(unselected), 'removed_reason'] = 'not_selected'
    report['sim_status'] = report['sim_status'].fillna('unknown')

    # keep reasons of a previous post-processing run (removed files cannot be checked again)
    if os.path.exists(report_path):
        previous = pd.read_csv(report_path, usecols=['sim_idx', 'removed_reason'], keep_default_na=False).set_index('sim_idx')['removed_reason']
        prev_reason = report['sim_idx'].map(previous)
        keep_previous = (report['removed_reason'] == 'missing_result') & prev_reason.notna() & (prev_reason != '') & (prev_reason != 'missing_result')
        report.loc[keep_previous, 'removed_reason'] = prev_reason[keep_previous]

    report['removed_reason'] = report['removed_reason'].fillna('')
    report.to_csv(report_path, index=False)
    print(f"  Status report: {report['removed_reason'].replace('', 'retained').value_counts().to_dict()}")
    return report_path


def post_process_dataset(dataset_path, n_target=0, seed=0):
    """
    Post-process dataset:
    1. Filter failed simulations (no success reported or no result file)
    2. Filter simulations with voltage violations or implausible waveforms
    3. If n_target > 0: select exactly n_target simulations, preserving the planned event shares
    4. Write a per-simulation status report (labels/sim_status.csv)
    """
    all_setting_files = glob.glob(os.path.join(dataset_path, "**", "settings.csv"), recursive=True)

    for setting_file in tqdm(all_setting_files):
        print(f"\nProcessing: {setting_file}")
        sim_status = collect_sim_status(os.path.dirname(setting_file))

        # Step 1: Filter failed simulations
        clean_file = filter_failed_simulations(setting_file, sim_status)
        print(f"  After failed filter: {len(pd.read_csv(clean_file))} simulations")

        # Step 2: Filter voltage violations and implausible waveforms
        checks = filter_voltage_violations(clean_file)
        print(f"  After voltage filter: {len(pd.read_csv(clean_file))} simulations")

        # Step 3: Select the target number of simulations
        unselected = select_target_number(setting_file, n_target, seed) if n_target else []

        # Step 4: Status report
        write_status_report(setting_file, sim_status, checks, unselected)


if __name__ == "__main__":
    # main_datagen.py runs the post-processing after the simulations; this is only needed to repeat it. Do not run it on
    # datasets whose result paths were made relative (util/convert_result_paths.py): every simulation would be missing.
    parser = argparse.ArgumentParser(description="Post-process a generated dataset.")
    parser.add_argument("--dataset_path", type=str, required=True)
    parser.add_argument("--n_target", type=int, default=0, help="number of simulations to select (0: keep all retained)")
    args = parser.parse_args()
    post_process_dataset(args.dataset_path, n_target=args.n_target)
