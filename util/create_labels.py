"""
Creates labels/labels.csv from labels/settings_clean.csv.

settings_clean.csv contains every sampled parameter of a simulation, also those that util/parallel_sim_handler.py does
not apply in PowerFactory or that cannot affect the simulated event (e.g. the arc parameters of a fault without arc, the
capacitor power of a line fault, the phase selection of a three-phase fault). labels.csv has the same rows
and the same values, but a value is only kept if it is applied in PowerFactory and can affect the simulation; all other
values are empty. Columns that are empty for every simulation of a dataset are left out. Values are copied as text, so
kept values are identical to settings_clean.csv.

Rules (see the corresponding functions in util/parallel_sim_handler.py):
- events: fault resistance R_f = event_flt_shc_resistance for short circuits (all types, also with arc),
  event_flt_hif_resistance for high-impedance and incipient faults; line location only for faults on lines (not on
  buses); 2-phase selection for 2ph/2phg faults, 1-phase selection for 1phg faults (none for 3ph faults); fault duration
  only for incipient faults; arc parameters only for faults with arc.
- auxiliary equipment (switched capacitor, OHL, cable, inrush transformers, motor and the switched load LdSwitch /
  LoadSwitch) is only connected to the grid by the EventConnector during its own switching event, so its parameters are
  only kept for that event. The cable is only applied in 20 kV grids, the HV inrush transformer not in 345 kV grids,
  the motor only in 20/110 kV grids (and switch_motor_start only exists in 20 kV grids).
- grounding: only applied if the grid contains StarpointPermRes.ElmVac and PetersenCoil.ElmVac (multi_grid 20 and
  110 kV, created by create_slack; not the benchmark models used for adapt_grid), and only the parameters of the
  sampled grounding type.
- ExtGrid: only applied if the main grid contains an ElmXnet (all grids except IEEE39BusSystem).
- dispatch/locality_factor and dispatch/power_share are not set in PowerFactory (only used to compute pgen) and are
  left empty. gens/*/pgen is the sampled setpoint; note that the load flow limits it to Pmax_uc of the machine.

Usage: python util/create_labels.py --dataset_path <dataset folder or folder with several datasets>
Requires pandas and networkx (no PowerFactory).
"""
import argparse
import glob
import os
import pickle
import re

import pandas as pd

SHC_EVENTS = {"flt_1phg_shc", "flt_1phg_shc_w_arc", "flt_2ph_shc", "flt_2phg_shc", "flt_3ph_shc"}
HIF_RESISTANCE_EVENTS = {"flt_1phg_hif", "flt_1phg_hif_w_arc", "flt_1phg_incipient", "flt_1phg_incipient_w_arc"}
FAULT_EVENTS = SHC_EVENTS | HIF_RESISTANCE_EVENTS
PHASE_2PH_EVENTS = {"flt_2ph_shc", "flt_2phg_shc"}
PHASE_1PH_EVENTS = {"flt_1phg_shc", "flt_1phg_shc_w_arc", "flt_1phg_hif", "flt_1phg_hif_w_arc", "flt_1phg_incipient",
                    "flt_1phg_incipient_w_arc"}
INCIPIENT_EVENTS = {"flt_1phg_incipient", "flt_1phg_incipient_w_arc"}
ARC_EVENTS = {"flt_1phg_shc_w_arc", "flt_1phg_hif_w_arc", "flt_1phg_incipient_w_arc"}
SWITCH_EVENTS = {"switch_inrushLV", "switch_inrushHV", "switch_load_on", "switch_load_off", "switch_cap_on",
                 "switch_cap_off", "switch_ohl_on", "switch_ohl_off", "switch_cable_on", "switch_cable_off",
                 "switch_motor_start", "switch_ibr_trip", "switch_gen_trip"}
KNOWN_EVENTS = FAULT_EVENTS | SWITCH_EVENTS

# loads behind the load switch of the switch_load_on/off events (they are in the main grid and therefore get load
# settings, but are only connected during these events)
SWITCHED_LOADS = {"LdSwitch", "LoadSwitch"}

# Elements of the PowerFactory models that decide whether the grounding and external grid settings are applied
# (checked with PowerFactory 2025 SP4 on models/*.pfd; multi_grid: grounding elements are created by create_slack in
# setting_generation/generate_dynamic_grid_settings.py for vn != 345 kV, the external grid "Slack" for all grids).
GRID_MODELS = {
    "CigreMVGrid":     {"grounding": False, "ext_grid": True},
    "DoubleLine":      {"grounding": False, "ext_grid": True},
    "TestGrid110kV":   {"grounding": False, "ext_grid": True},
    "IEEE39BusSystem": {"grounding": False, "ext_grid": False},
    "Template20kV":    {"grounding": True,  "ext_grid": True},
    "Template110kV":   {"grounding": True,  "ext_grid": True},
    "Template345kV":   {"grounding": False, "ext_grid": True},
}

# columns that parallel_sim_handler.py never reads ("Unnamed: 0" is the index of settings.csv, equal to sim_idx)
DROPPED_COLUMNS = ["Unnamed: 0", "events/event_iflt_arc_on"]


def get_grid_name(label_path):
    """the dataset folder (parent of labels/) is named after the model, e.g. .../adapt_grid/CigreMVGrid/labels"""
    return os.path.basename(os.path.dirname(os.path.abspath(label_path)))


class TargetClassifier:
    """Decides whether a fault target is a line (the fault location is applied) or a bus, using the grid graphs."""

    def __init__(self, graph_path):
        self.graph_path = graph_path
        self.graphs = {}

    def is_line(self, graph_name, target):
        if graph_name not in self.graphs:
            path = os.path.join(self.graph_path, graph_name)
            if os.path.exists(path):
                with open(path, 'rb') as f:
                    graph = pickle.load(f)
                self.graphs[graph_name] = (set(graph.nodes), {key for _, _, key in graph.edges(keys=True)})
            else:
                print(f"  WARNING: {path} not found, fault targets are classified by name (MainLn... = line)")
                self.graphs[graph_name] = None
        if self.graphs[graph_name] is None:
            return "Ln" in target
        buses, branches = self.graphs[graph_name]
        if target in buses:
            return False
        if target in branches:
            return True
        raise ValueError(f"Fault target {target} is neither a bus nor a line of {graph_name}")


def applied_mask(df, column, grid, classifier):
    """Boolean Series: True where the value of column is applied in PowerFactory."""
    event = df["events/event_type"]
    vn = df["general/vn"].astype(float)
    every = pd.Series(True, index=df.index)

    if column.startswith("general/") or column in ("events/event_type", "events/event_start", "events/event_target"):
        return every

    if column == "events/event_flt_target_line_location":
        is_fault = event.isin(FAULT_EVENTS)
        is_line = pd.Series([is_fault[i] and classifier.is_line(df.at[i, "general/grid_graph"], df.at[i, "events/event_target"])
                             for i in df.index], index=df.index)
        return is_fault & is_line
    if column == "events/event_flt_shc_resistance":
        return event.isin(SHC_EVENTS)
    if column == "events/event_flt_hif_resistance":
        return event.isin(HIF_RESISTANCE_EVENTS)
    if column == "events/event_phase_select_2ph":
        return event.isin(PHASE_2PH_EVENTS)
    if column == "events/event_phase_select_1ph":
        return event.isin(PHASE_1PH_EVENTS)
    if column == "events/event_iflt_duration":
        return event.isin(INCIPIENT_EVENTS)
    if column.startswith("arc/"):
        return event.isin(ARC_EVENTS)

    if column.startswith("cap_switch/"):
        return event.isin({"switch_cap_on", "switch_cap_off"})
    if column.startswith("ohl_switch/"):
        return event.isin({"switch_ohl_on", "switch_ohl_off"})
    if column.startswith("cable_switch/"):
        return event.isin({"switch_cable_on", "switch_cable_off"}) & (vn == 20)
    if column == "switch_trafo_to_lv_type":
        return event == "switch_inrushLV"
    if column == "switch_trafo_to_hv_type":
        return (event == "switch_inrushHV") & (vn != 345)
    if column.startswith("motor_start/"):
        return (event == "switch_motor_start") & vn.isin([20, 110])

    if column.startswith("loads/"):
        load_name = column.split("/")[1]
        if load_name in SWITCHED_LOADS:
            return event.isin({"switch_load_on", "switch_load_off"})
        return every  # empty for loads of other topologies (multi_grid)

    if column.startswith("gens/"):
        gen_name = column.split("/")[1]
        return (vn >= 110) & (df[f"gens/{gen_name}/pgen"] != "")
    if column.startswith("dispatch/"):
        return ~every

    if column.startswith("grounding/"):
        if not grid_info(grid, column)["grounding"]:
            return ~every
        grnd_type = df["grounding/grnd_type"]
        return {
            "grounding/grnd_type": every,
            "grounding/solid_ground_resistance": grnd_type == "solid",
            "grounding/resistive_ground_resistance": grnd_type == "resistive",
            "grounding/coil_tuning": grnd_type == "resonant",
            "grounding/parasitic_resistance_percentage": grnd_type == "resonant",
        }[column]
    if column.startswith("ExtGrid/"):
        return every if grid_info(grid, column)["ext_grid"] else ~every

    raise KeyError(f"No rule for column {column}: add it to create_labels.py (applied_mask)")


def grid_info(grid, column):
    if grid not in GRID_MODELS:
        raise KeyError(f"Unknown grid {grid} (needed for {column}): add it to GRID_MODELS in create_labels.py "
                       f"or pass --grid with the model name")
    return GRID_MODELS[grid]


def read_settings(setting_file):
    """settings as text: kept values are written back unchanged, empty cells are \"\" """
    return pd.read_csv(setting_file, dtype=str, keep_default_na=False)


def make_labels(df, grid, graph_path):
    """
    Labels of a settings table read with read_settings (no file is written). graph_path is the graphs/ folder of the
    dataset (used to tell line from bus fault targets). Returns the labels and the number of emptied values per column.
    """
    unknown_events = set(df["events/event_type"]) - KNOWN_EVENTS
    if unknown_events:
        raise ValueError(f"Unknown event types {unknown_events}: add them to create_labels.py")

    classifier = TargetClassifier(graph_path)
    labels = df.drop(columns=[c for c in DROPPED_COLUMNS if c in df.columns])
    blanked = {}
    for column in labels.columns:
        mask = applied_mask(df, column, grid, classifier)
        n_blanked = int(((labels[column] != "") & ~mask).sum())
        if n_blanked:
            blanked[column] = n_blanked
        labels.loc[~mask, column] = ""
    return labels, blanked


def create_labels(setting_file_clean, grid=None):
    label_path = os.path.dirname(setting_file_clean)
    grid = grid or get_grid_name(label_path)
    df = read_settings(setting_file_clean)
    labels, blanked = make_labels(df, grid, os.path.join(os.path.dirname(label_path), 'graphs'))
    empty_columns = [c for c in labels.columns if (labels[c] == "").all()]
    labels = labels.drop(columns=empty_columns)

    labels_file = os.path.join(label_path, 'labels.csv')
    labels.to_csv(labels_file, index=False)

    print(f"{setting_file_clean} ({grid}): {len(labels)} simulations -> {labels_file}")
    dropped = [c for c in DROPPED_COLUMNS if c in df.columns] + empty_columns
    if dropped:
        print(f"  dropped columns: {dropped}")
    groups = {}
    for column, n in blanked.items():
        group = re.sub(r"^loads/(?!LdSwitch/|LoadSwitch/)[^/]+/", "loads/*/", column)
        group = re.sub(r"^gens/[^/]+/", "gens/*/", group)
        groups[group] = groups.get(group, 0) + n
    for group, n in groups.items():
        print(f"  emptied {n:7d} values of {group}")
    return labels_file


def main():
    parser = argparse.ArgumentParser(description='Create labels/labels.csv (applied settings only) from settings_clean.csv.')
    parser.add_argument('--dataset_path', type=str, required=True, help='dataset folder or folder with several datasets')
    parser.add_argument('--grid', type=str, default=None,
                        help=f'model name if the dataset folder is not named after it, one of {list(GRID_MODELS)}')
    args = parser.parse_args()

    setting_files = sorted(glob.glob(os.path.join(args.dataset_path, "**", "settings_clean.csv"), recursive=True))
    if not setting_files:
        raise FileNotFoundError(f"No settings_clean.csv found in {args.dataset_path}")
    if args.grid and len(setting_files) > 1:
        raise ValueError("--grid can only be used for a single dataset")
    for setting_file in setting_files:
        create_labels(setting_file, args.grid)


if __name__ == '__main__':
    main()
