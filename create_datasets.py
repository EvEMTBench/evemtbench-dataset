"""
Generates the EvEMTBench datasets from scratch and brings them into the published form. Steps (--steps, default: all, in
this order):
  libs      type libraries (cables, conductors, loads, overhead line towers, machines, transformers; seed 0) in the
            CustomTypeLib folder of the PowerFactory user (parameter_sampling/generate_*.py)
  models    prepares the grid models in models/*.pfd for this machine (measurements, result export, simulation settings,
            paths of the IBR controller FMU and of util/parallel_sim_handler.py; util/pf_prepare_models.py)
  simulate  samples the settings, runs the simulations and post-processes every dataset (main_datagen.py); the result is
            in <data_dir>/<subset>/<grid>
  publish   published form of every dataset: relative result paths (util/convert_result_paths.py), labels/labels.csv
            (util/create_labels.py), and all files that are not published moved to <not_released_dir>
            (util/move_unreleased_files.py)
  splits    train / val / test splits of the multigrid and adapt_grid datasets (reference_implementation/split_datasets.py)

Usage: python create_datasets.py [--data_dir <folder>] [--not_released_dir <folder>] [--pf_python_path <folder>]
                                 [--model_dir <folder>] [--steps libs models simulate publish splits]
                                 [--datasets multi_grid/Template20kV ...] [--chunk_size 128]
Requires Windows with PowerFactory 2025 SP4 and the packages in requirements.txt (see readme.md). All datasets with all
files need about 2.5 TB.
"""
import argparse
import os
import subprocess
import sys
import time

REPO_DIR = os.path.dirname(os.path.abspath(__file__))

# Definition of the published datasets: grid model, number of planned simulations and, for multi_grid, the number of
# simulations per generated topology (determines the dataset). adapt_grid and multi_grid: more simulations are planned
# than needed and the post-processing selects exactly N_TARGET of the retained simulations, preserving the planned event
# shares (util/post_processing.py, select_target_number). Benchmark datasets are complete sweeps.
DATASETS = {
    # subset/grid: (model, max_simulations)
    "multi_grid/Template20kV": ("Template20kV.pfd", 12096),  # 126 topologies
    "multi_grid/Template110kV": ("Template110kV.pfd", 13440),  # 140 topologies
    "multi_grid/Template345kV": ("Template345kV.pfd", 12096),  # 126 topologies
    "adapt_grid/CigreMVGrid": ("CigreMVGrid.pfd", 12500),
    "adapt_grid/DoubleLine": ("DoubleLine.pfd", 11000),
    "adapt_grid/TestGrid110kV": ("TestGrid110kV.pfd", 15000),
    "adapt_grid/IEEE39BusSystem": ("IEEE39BusSystem.pfd", 12000),
    "benchmark/CigreMVGrid": ("CigreMVGrid.pfd", 10000),
    "benchmark/DoubleLine": ("DoubleLine.pfd", 10000),
    "benchmark/TestGrid110kV": ("TestGrid110kV.pfd", 10000),
    "benchmark/IEEE39BusSystem": ("IEEE39BusSystem.pfd", 10000),
}
CHUNK_SIZE_MULTIGRID = 96  # multi_grid: simulations per generated topology
N_TARGET = 10000  # adapt_grid and multi_grid: number of released simulations
DTEMT = 1e-5  # EMT integration step size in s
FS_EXPORT = 9600  # sampling rate of the exported results in Hz
LIBRARY_SCRIPTS = ["generate_cable_lib.py", "generate_conductor_data.py", "generate_load_types.py", "generate_ohl_types.py",
                   "generate_sym_lib.py", "generate_trafo_lib.py"]
SPLIT_DATASETS = [d for d in DATASETS if not d.startswith("benchmark")]
STEPS = ["libs", "models", "simulate", "publish", "splits"]


def run(command, env, log_file=None):
    print("Running:", " ".join(command), flush=True)
    subprocess.run(command, env=env, cwd=REPO_DIR, check=True, stdout=log_file, stderr=subprocess.STDOUT if log_file else None)


def main():
    parser = argparse.ArgumentParser(description="Generate the EvEMTBench datasets and bring them into the published form.")
    parser.add_argument("--data_dir", default=os.path.join(REPO_DIR, "datasets"), help="output folder of the datasets")
    parser.add_argument("--not_released_dir", default=os.path.join(REPO_DIR, "datasets_not_released"),
                        help="folder for the files that are not published (same drive as --data_dir, outside of it)")
    parser.add_argument("--pf_python_path", default=r"C:\Program Files\DIgSILENT\PowerFactory 2025 SP4\Python\3.9",
                        help="Python folder of the PowerFactory installation (contains the powerfactory module)")
    parser.add_argument("--model_dir", default=os.path.join(REPO_DIR, "models"),
                        help="folder with the grid models (*.pfd) and IBRviaFMU/; the step models prepares and overwrites the models in it")
    parser.add_argument("--steps", nargs="+", choices=STEPS, default=STEPS, help="steps to run (always in the order above)")
    parser.add_argument("--datasets", nargs="+", choices=list(DATASETS), default=list(DATASETS), metavar="SUBSET/GRID",
                        help=f"datasets to generate and publish (default: all), from {', '.join(DATASETS)}")
    parser.add_argument("--chunk_size", type=int, default=128,
                        help="adapt_grid and benchmark: simulations run in parallel (depends on the machine; does not change the datasets)")
    parser.add_argument("--debug", action="store_true", help="short simulations for testing (not the published datasets)")
    parser.add_argument("--showpf", action="store_true", help="show the PowerFactory window")
    args = parser.parse_args()
    data_dir, not_released_dir, model_dir = os.path.abspath(args.data_dir), os.path.abspath(args.not_released_dir), os.path.abspath(args.model_dir)
    if not os.path.isdir(args.pf_python_path):
        parser.error(f"--pf_python_path {args.pf_python_path} does not exist")
    debug, showpf = str(args.debug), str(args.showpf)

    # the scripts import from util/, setting_generation/ and parameter_sampling/ and import powerfactory, so the repository
    # and the Python folder of PowerFactory must be on the import path of every subprocess
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(p for p in [REPO_DIR, args.pf_python_path, os.environ.get("PYTHONPATH", "")] if p))
    t_start = time.time()

    if "libs" in args.steps:
        for script in LIBRARY_SCRIPTS:
            run([sys.executable, os.path.join(REPO_DIR, "parameter_sampling", script)], env)
        time.sleep(30)  # PowerFactory once aborted (rc 6001) when the next script started right after the library scripts

    if "models" in args.steps:
        run([sys.executable, os.path.join(REPO_DIR, "util", "pf_prepare_models.py"), "--debug", debug, "--dtemt", str(DTEMT),
             "--fs_export", str(FS_EXPORT), "--model_dir", model_dir], env)

    if "simulate" in args.steps:
        os.makedirs(data_dir, exist_ok=True)
        with open(os.path.join(data_dir, "all_runs.log"), "a") as log_file:
            for dataset in args.datasets:
                subset = dataset.split("/")[0]
                model, max_simulations = DATASETS[dataset]
                command = [sys.executable, os.path.join(REPO_DIR, "main_datagen.py"),
                           "--dataset_path", os.path.join(data_dir, *dataset.split("/")),
                           "--max_simulations", str(max_simulations),
                           "--sim_file_path", os.path.join(model_dir, model),
                           "--dataset_type", subset,
                           "--debug", debug,
                           "--showpf", showpf,
                           "--chunk_size", str(CHUNK_SIZE_MULTIGRID if subset == "multi_grid" else args.chunk_size),
                           "--dtemt", str(DTEMT), "--fs_export", str(FS_EXPORT)]
                if subset != "benchmark":
                    command += ["--n_target", str(N_TARGET)]
                log_file.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} {dataset}\n")
                log_file.flush()
                run(command, env, log_file)

    if "publish" in args.steps:
        for dataset in args.datasets:
            dataset_dir = os.path.join(data_dir, *dataset.split("/"))
            if not os.path.exists(os.path.join(dataset_dir, "labels", "settings_clean.csv")):
                print(f"{dataset}: no labels/settings_clean.csv, already in the published form or not generated, skipped")
                continue
            run([sys.executable, os.path.join(REPO_DIR, "util", "convert_result_paths.py"), "--dataset_path", dataset_dir, "--apply"], env)
            run([sys.executable, os.path.join(REPO_DIR, "util", "create_labels.py"), "--dataset_path", dataset_dir], env)
            run([sys.executable, os.path.join(REPO_DIR, "util", "move_unreleased_files.py"), "--dataset_path", dataset_dir,
                 "--target_path", os.path.join(not_released_dir, *dataset.split("/")), "--apply"], env)

    if "splits" in args.steps:
        missing = [d for d in SPLIT_DATASETS if not os.path.exists(os.path.join(data_dir, *d.split("/"), "labels", "labels.csv"))]
        if missing:
            print(f"Splits skipped, these datasets are not in the published form in {data_dir}: {missing}")
        else:
            run([sys.executable, os.path.join(REPO_DIR, "reference_implementation", "split_datasets.py"), "--dataset_path", data_dir], env)

    print(f"Time elapsed: {time.time() - t_start:.0f} s")


if __name__ == "__main__":
    main()
