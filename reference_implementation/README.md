# Reference implementation

Both scripts need only Python 3.9 or newer and the released data (no PowerFactory):
`pip install numpy pandas networkx scikit-learn tqdm`. `<datasets>` is the folder into which the archives were
extracted, e.g. `<datasets>/multi_grid/Template110kV` with `data/`, `graphs/` and `labels/`.

## Dataset splits

`split_datasets.py` splits every multigrid and adapt_grid dataset 80/10/10 into train, validation and test (seed 0):
multigrid by topology (`general/grid_graph`), adapt_grid by simulation. Benchmark datasets are meant for testing only.
The result is `splits/<subset>-<grid>.csv` with the columns `sim_idx` and `split` (`train`, `val`, `test`); the files
are included.

```bash
python split_datasets.py --dataset_path <datasets>
```

## Faulted phase detection

`fault_phase_detection.py` is a minimal training example:

- **Task:** which phases are involved in a short circuit on a line (1PHG, 2PH, 2PHG, 3PH, without arc).
- **Data:** multigrid 110 kV with its split file (validation and test topologies are unseen), plus the benchmark
  DoubleLine grid as an additional test set.
- **Input:** phase voltages and currents at both ends of the faulted line (`bus_1`, `bus_2` of the line in the graph),
  40 ms (384 samples) from fault inception. Gaussian white noise with 50 dB SNR is added to every channel, which we
  recommend for all uses of the data; each window is then normalised (voltages and currents separately).
- **Model:** scikit-learn `MLPClassifier` with default settings (seed 0), one output per phase.

```bash
python fault_phase_detection.py --dataset_path <datasets>
```

It needs `multi_grid-Template110kV.tar.gz` and `benchmark-DoubleLine.tar.gz`, reads 2,548 result files (about 6 min)
and prints confusion matrices of the faulted phases for the validation and test sets and for DoubleLine. All 209
validation, 172 test and 600 DoubleLine faults are classified correctly.
