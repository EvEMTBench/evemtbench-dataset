"""
Moves everything that is not part of the published datasets out of the dataset folders. The published datasets are made
for training and contain data/, graphs/ and labels/labels.csv. Moved are:
- data_unselected/: result files of retained simulations that were not selected (removed_reason not_selected in
  labels/sim_status.csv)
- labels/status/: one status file per simulation; their content is merged into labels/sim_status.csv by
  util/post_processing.py
- labels/settings.csv, settings_clean.csv, event_selection.csv and sim_status.csv: all planned simulations, all sampled
  parameters and the outcome of every planned simulation. Analyses of the generated datasets (e.g. of the removed
  simulations) need them, so run those before moving the files.

Everything is moved to <target_path>/<same relative path>, so nothing is deleted and it can be moved back. The target
must be on the same drive as the datasets (folders and files are renamed, nothing is copied) and outside of --dataset_path.

Without --apply, everything is only checked and nothing is moved. labels.csv must exist and hold exactly the released
simulations, and the files in the two folders must be exactly those expected from labels/sim_status.csv, otherwise the
script stops before anything of any dataset is moved. What is already in the target is skipped, so the script can be
started again after an interruption.

Usage: python util/move_unreleased_files.py --dataset_path <folder with one or several datasets> --target_path <folder> [--apply]
No third-party packages required.
"""
import argparse
import csv
import glob
import os

UNSELECTED_FOLDER = "data_unselected"
STATUS_FOLDER = os.path.join("labels", "status")
LABEL_FILES = ["settings.csv", "settings_clean.csv", "event_selection.csv", "sim_status.csv"]  # sim_status.csv is read by this script: last
OPTIONAL_LABEL_FILES = {"event_selection.csv"}  # benchmark datasets have none


def read_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def expected_files(folder, status):
    """names of the files that labels/sim_status.csv expects in the folder"""
    if folder == UNSELECTED_FOLDER:
        return {f"result{row['sim_idx']}.csv" for row in status if row["removed_reason"] == "not_selected"}
    return {f"sim_status_{row['sim_idx']}.csv" for row in status if row["sim_status"] != "unknown"}


def read_status(dataset_dir, dataset_in_target):
    """labels/sim_status.csv of a dataset, from the target if an earlier run has already moved it"""
    for folder in (dataset_dir, dataset_in_target):
        path = os.path.join(folder, "labels", "sim_status.csv")
        if os.path.exists(path):
            return read_rows(path)
    raise ValueError(f"no labels/sim_status.csv for {dataset_dir}")


def plan_moves(dataset_path, target_path):
    """checks all datasets and returns [(source, destination, number of files)]; raises ValueError if something does not fit"""
    label_folders = sorted(p for p in glob.glob(os.path.join(dataset_path, "**", "labels"), recursive=True) if os.path.isdir(p))
    if not label_folders:
        raise FileNotFoundError(f"No labels folder found in {dataset_path}")

    moves = []
    for label_folder in label_folders:
        dataset_dir = os.path.dirname(label_folder)
        dataset_in_target = os.path.join(target_path, os.path.relpath(dataset_dir, dataset_path))
        labels_file = os.path.join(label_folder, "labels.csv")
        if not os.path.exists(labels_file):
            raise ValueError(f"{labels_file} is missing: create it before moving the files it is made from")
        status = read_status(dataset_dir, dataset_in_target)
        released = {row["sim_idx"] for row in status if row["removed_reason"] == ""}
        if {row["general/sim_idx"] for row in read_rows(labels_file)} != released:
            raise ValueError(f"{labels_file} does not hold exactly the {len(released)} released simulations of labels/sim_status.csv")

        for folder in (UNSELECTED_FOLDER, STATUS_FOLDER):
            source, destination = os.path.join(dataset_dir, folder), os.path.join(dataset_in_target, folder)
            expected = expected_files(folder, status)
            if os.path.exists(source) and os.path.exists(destination):
                raise ValueError(f"{source} and {destination} both exist")
            if os.path.exists(destination):
                continue
            if not os.path.exists(source):
                if expected:
                    raise ValueError(f"{source} is missing, labels/sim_status.csv expects {len(expected)} files in it")
                continue
            files = set(os.listdir(source))
            if files != expected:
                raise ValueError(f"{source}: {len(files - expected)} unexpected and {len(expected - files)} missing files, e.g. {sorted(files ^ expected)[:3]}")
            moves.append((source, destination, len(files)))

        for name in LABEL_FILES:
            source, destination = os.path.join(label_folder, name), os.path.join(dataset_in_target, "labels", name)
            if os.path.exists(source) and os.path.exists(destination):
                raise ValueError(f"{source} and {destination} both exist")
            if os.path.exists(source):
                moves.append((source, destination, 1))
            elif not os.path.exists(destination) and name not in OPTIONAL_LABEL_FILES:
                raise ValueError(f"{source} is missing")
    return moves


def main():
    parser = argparse.ArgumentParser(description="Move everything except data/, graphs/ and labels/labels.csv out of the dataset folders.")
    parser.add_argument("--dataset_path", type=str, required=True, help="dataset folder or folder with several datasets")
    parser.add_argument("--target_path", type=str, required=True, help="folder for the moved files, on the same drive and outside of dataset_path")
    parser.add_argument("--apply", action="store_true", help="move the files (without it, everything is only checked)")
    args = parser.parse_args()

    dataset_path, target_path = os.path.abspath(args.dataset_path), os.path.abspath(args.target_path)
    if os.path.splitdrive(dataset_path)[0].lower() != os.path.splitdrive(target_path)[0].lower():
        parser.error("--target_path must be on the same drive as --dataset_path (folders and files are renamed, not copied)")
    if os.path.normcase(os.path.commonpath([dataset_path, target_path])) == os.path.normcase(dataset_path):
        parser.error("--target_path must be outside of --dataset_path")

    # everything of all datasets is checked before the first move
    moves = plan_moves(dataset_path, target_path)
    for source, _, n_files in moves:
        print(f"{os.path.relpath(source, dataset_path)}: {n_files} files")
    n_files = sum(n for _, _, n in moves)
    if not args.apply:
        print(f"\nAll checks passed, {len(moves)} folders and files with {n_files} files in total would be moved to {target_path}. Nothing was moved, use --apply to move them.")
        return
    for source, destination, _ in moves:
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        os.rename(source, destination)
    print(f"\nMoved {len(moves)} folders and files with {n_files} files in total to {target_path}.")


if __name__ == "__main__":
    main()
