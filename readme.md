# EvEMTBench

EvEMTBench is a dataset of 85,554 electromagnetic transient (EMT) simulations of power system events (switching
operations, short circuits, high-impedance and incipient faults) in grids from 20 kV to 345 kV, simulated with
DIgSILENT PowerFactory. This repository contains the code that generated the dataset and a minimal reference
implementation, that can be used as an example on how to use the data.

- **Data:** FAUDataCloud, https://doi.org/10.48742/fau.3383-vd93. One archive per dataset (`<subset>-<grid>.tar.gz`, subsets `multi_grid`, `adapt_grid`,
  `benchmark`), each with `data/result<sim_idx>.csv` (voltages and currents, 9.6 kHz), `graphs/` (grid graph as
  networkx pickle and PowerFactory `.pfd`) and `labels/labels.csv` (one row per simulation: operating state, event and
  file references).
- **Code archive:** Zenodo, https://doi.org/10.5281/zenodo.21624649 (the released dataset was generated with version
  V1.0).
- **Paper:** Kordowich, G. et al. *A simulation based dataset of faults and events for machine learning in power
  systems* (submitted to Scientific Data).
- **Licence:** code CC0 1.0 Universal (see `LICENSE`), data CC BY 4.0. The grid models `models/CigreMVGrid.pfd` and
  `models/IEEE39BusSystem.pfd` are based on the PowerFactory application examples "MV Microgrid" and "39 Bus New
  England System" by DIgSILENT GmbH, which permitted their publication.

## Repository structure

| Folder / file | Content |
|---|---|
| `create_datasets.py` | Orchestrator: runs all steps below |
| `main_datagen.py` | One dataset: samples the settings, runs the simulations in PowerFactory, post-processes the results |
| `models/` | Grid models (`.pfd`), `CustomTypeLib.pfd` (block definitions) and the IBR controller (`IBRviaFMU/`) |
| `parameter_sampling/` | Generation of the type libraries; random sampling of topologies, operating states and events |
| `setting_generation/` | Generation of the simulation settings per dataset |
| `util/` | PowerFactory helpers, model preparation, graph and label creation, post-processing |
| `reference_implementation/` | Faulted phase detection example and the train/val/test splits, see its `README.md` |

## Requirements

- Windows with DIgSILENT PowerFactory 2025 SP4 (EMT simulation) and its Python 3.9 API
- The packages in `requirements.txt`, importable by the Python that runs `create_datasets.py` and by PowerFactory's
  Python
- `models/CustomTypeLib.pfd` imported into the PowerFactory user folder
- To run a script on its own, put the repository root and the PowerFactory Python folder on `PYTHONPATH`
  (`create_datasets.py` does this for the scripts it starts)

The reference implementation needs only Python and the released data, no PowerFactory.

## Regenerating the dataset

```bash
python create_datasets.py --data_dir <output> --pf_python_path "C:\Program Files\DIgSILENT\PowerFactory 2025 SP4\Python\3.9"
```

Steps (select with `--steps`, default all):

1. `libs`: generate the type libraries (cables, conductors, loads, overhead lines, machines, transformers) in the
   PowerFactory user folder (`parameter_sampling/`).
2. `models`: prepare the grid models in `models/` for this machine (measurements, export, simulation settings, paths of
   the IBR controller FMU and of `util/parallel_sim_handler.py`; `util/pf_prepare_models.py`).
3. `simulate`: per dataset, `main_datagen.py` samples the settings, runs the simulations in parallel and post-processes
   the results (`util/post_processing.py`).
4. `publish`: bring every dataset into the published form (relative result paths, `labels/labels.csv`); all other
   files are moved to `--not_released_dir` (same drive as `--data_dir`).
5. `splits`: train/val/test splits (`reference_implementation/split_datasets.py`).

`--datasets SUBSET/GRID ...` restricts the run to single datasets, `--chunk_size` sets the number of adapt_grid and
benchmark simulations run in parallel (default 128; does not change the data), `--model_dir` points to another model
folder. Multigrid datasets always use 96 simulations per topology (`CHUNK_SIZE_MULTIGRID`), as this defines the
dataset. The datasets
themselves (models, planned simulations, 10,000 released simulations, 10 µs step size, 9.6 kHz export) are defined at
the top of `create_datasets.py`. All sampling is seeded (seed 0), so a complete run from scratch reproduces the
released datasets, except for rare simulations that PowerFactory non-reproducibly aborts. All datasets with all files need about
2.5 TB. The duration of a full run depends on the hardware, but can take between few days and several weeks.

**Post-processing** keeps only successful simulations with a result file and removes simulations whose RMS voltage
in the first two exported cycles is outside 0.9–1.1 pu, which show a growing DC current before the event, exceed a
peak voltage of 5 pu, or are not in steady state before the event. From the remaining simulations, 10,000 are selected per dataset with a fixed seed, keeping the share of
each event type.
