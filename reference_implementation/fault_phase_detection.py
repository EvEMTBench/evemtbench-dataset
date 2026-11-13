"""
Minimal reference workflow for EvEMTBench: detect the faulted phases of line short circuits with a small neural network
(multilayer perceptron, scikit-learn defaults: one hidden layer with 100 neurons).
Trained on the train set of multigrid 110 kV and evaluated on its val and test sets (split by topology, from
splits/multi_grid-Template110kV.csv, written by split_datasets.py) and on the unseen benchmark DoubleLine grid (110 kV).
Input: voltages and currents at both ends of the faulted line (bus_1, bus_2), 40 ms after fault inception, with Gaussian
white noise of SNR_DB added to every channel (so that the model cannot rely on numerical simulation artifacts), normalised
per window (one mean and standard deviation for all voltage channels, one for all current channels).
Usage: python fault_phase_detection.py --dataset_path <folder with the extracted datasets (multi_grid/Template110kV,
benchmark/DoubleLine)>
Requires numpy, pandas, networkx, scikit-learn and tqdm (no PowerFactory).
"""
import argparse
import os
import pickle

import numpy as np
import pandas as pd
from sklearn.neural_network import MLPClassifier
from tqdm import tqdm

parser = argparse.ArgumentParser(description="Train and evaluate the faulted phase detection.")
parser.add_argument("--dataset_path", required=True, help="folder with the extracted datasets (multi_grid/Template110kV, benchmark/DoubleLine)")
DATASET_PATH = parser.parse_args().dataset_path
TRAIN_DATASET = os.path.join(DATASET_PATH, "multi_grid", "Template110kV")
TEST_DATASET = os.path.join(DATASET_PATH, "benchmark", "DoubleLine")
SPLIT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "splits", "multi_grid-Template110kV.csv")
FAULT_TYPES = ["flt_1phg_shc", "flt_2ph_shc", "flt_2phg_shc", "flt_3ph_shc"]
FS = 9600  # sampling rate (Hz); the first sample is at t = 1 s
WINDOW = int(0.04 * FS)  # 40 ms after fault inception
SEED = 0
SNR_DB = 50  # signal-to-noise ratio of the added Gaussian white noise, per channel and window
VOLTAGES = ["c:Usec:A", "c:Usec:B", "c:Usec:C"]  # quantities in the second header row of the result files
CURRENTS = ["c:Isec:A", "c:Isec:B", "c:Isec:C"]
RNG = np.random.default_rng(SEED)


def add_noise(x):
    """Gaussian white noise to every channel (column) of x, with a noise power SNR_DB below the power of the channel"""
    rms = np.sqrt(np.mean(np.square(x), axis=0))
    return x + RNG.normal(size=x.shape) * rms / 10 ** (SNR_DB / 20)


def load_graph(path):
    with open(path, "rb") as f:
        return pickle.load(f)


def line_ends(dataset, row):
    """names of the measurements at both ends of the faulted line: [bus_1 end, bus_2 end]"""
    graph = load_graph(os.path.join(dataset, "graphs", row["general/grid_graph"]))
    line = row["events/event_target"]
    params = next(data[f"{line}_param_dict"] for _, _, key, data in graph.edges(keys=True, data=True) if key == line)
    return [f"pex_{params['bus_1']}_{line}", f"pex_{params['bus_2']}_{line}"]


def features(dataset, row):
    """40 ms of the phase voltages and currents at both line ends, normalised, as one feature vector"""
    # read the 40 ms after fault inception: file lines 0 and 1 are the two header rows and line 2 + k holds sample k
    # (sample 0 is at t = 1 s), so skip lines 2 to 2 + start - 1, the samples before the fault
    path = os.path.join(dataset, row["general/result_file_path"])
    start = round((row["events/event_start"] - 1.0) * FS)
    waveforms = pd.read_csv(path, header=[0, 1], skiprows=range(2, 2 + start), nrows=WINDOW)

    # the two header rows give each column's measurement and quantity, e.g. "Cub_1\pex_MainBus1_MainLn1-2" and
    # "c:Usec:A in V"; shorten them to ("pex_MainBus1_MainLn1-2", "c:Usec:A") to select columns by name
    waveforms.columns = pd.MultiIndex.from_tuples(
        [(measurement.split("\\")[-1], quantity.split(" ")[0]) for measurement, quantity in waveforms.columns])
    ends = line_ends(dataset, row)
    voltages = add_noise(waveforms[[(end, v) for end in ends for v in VOLTAGES]].to_numpy())  # 384 samples x 6 voltages
    currents = add_noise(waveforms[[(end, i) for end in ends for i in CURRENTS]].to_numpy())  # 384 samples x 6 currents

    # normalise with one mean and standard deviation for all voltages and one for all currents of this window
    voltages = (voltages - voltages.mean()) / voltages.std()
    currents = (currents - currents.mean()) / currents.std()
    return np.concatenate([voltages, currents], axis=1).T.ravel()  # 12 channels x 384 samples


def faulted_phases(row):
    """[a, b, c] faulted (True/False)"""
    if row["events/event_type"] == "flt_3ph_shc":
        phases = "abc"
    elif row["events/event_type"] == "flt_1phg_shc":
        phases = row["events/event_phase_select_1ph"]
    else:
        phases = row["events/event_phase_select_2ph"]
    return [p in phases for p in "abc"]


def phase_names(y):
    """faulted phases as text, e.g. [True, False, True] -> "ac" ("none" if no phase is faulted)"""
    return ["".join(p for p, faulted in zip("abc", phases) if faulted) or "none" for phases in y]


def load(dataset):
    labels = pd.read_csv(os.path.join(dataset, "labels", "labels.csv"), low_memory=False)
    faults = labels[labels["events/event_type"].isin(FAULT_TYPES) & labels["events/event_flt_target_line_location"].notna()]
    rows = tqdm(faults.iterrows(), total=len(faults), desc=f"Loading {os.path.basename(dataset)}")
    x = np.array([features(dataset, row) for _, row in rows], dtype=np.float32)
    y = np.array([faulted_phases(row) for _, row in faults.iterrows()])
    return x, y, faults["general/sim_idx"].to_numpy()


x, y, sim_idx = load(TRAIN_DATASET)
split = pd.read_csv(SPLIT_FILE).set_index("sim_idx")["split"].loc[sim_idx].to_numpy()
x_test, y_test, _ = load(TEST_DATASET)

print(f"Training the MLP on {(split == 'train').sum()} faults ...")
model = MLPClassifier(random_state=SEED).fit(x[split == "train"], y[split == "train"])
sets = {"val": (x[split == "val"], y[split == "val"]), "test": (x[split == "test"], y[split == "test"]),
        "DoubleLine": (x_test, y_test)}
for name, (x_set, y_set) in sets.items():
    true = pd.Series(phase_names(y_set), name="true")
    predicted = pd.Series(phase_names(model.predict(x_set)), name="predicted")
    print(f"\nConfusion matrix of the faulted phases, {name} ({len(y_set)} faults):")
    print(pd.crosstab(true, predicted))
