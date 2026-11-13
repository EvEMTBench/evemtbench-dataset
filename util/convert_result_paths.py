"""
Makes the result file paths in the labels of finished datasets relative.

general/result_file_path in labels/settings.csv, settings_clean.csv and (if it exists) labels.csv holds the absolute path
on the machine that generated the simulation. It is replaced by data/result<sim_idx>.csv, relative to the dataset folder
(the parent of labels/). Only this column changes: the files are edited as bytes, so all other values and the line
endings stay identical (reading and writing them with pandas would change the last digits of floats).

Without --apply, the files are only checked and nothing is written. Every path must be the result file of its own
simulation in this dataset (.../<dataset folder>/data/result<sim_idx>.csv), otherwise the script stops before any file of
any dataset is written. Paths that are already relative stay as they are, so the script can be started again after an
interruption.

Only use it on finished datasets: util/post_processing.py needs the absolute paths and must not be run on a converted
dataset (it would treat every simulation as missing and empty settings_clean.csv).

Usage: python util/convert_result_paths.py --dataset_path <dataset folder or folder with several datasets> [--apply]
No third-party packages required.
"""
import argparse
import csv
import glob
import io
import os

PATH_COLUMN = "general/result_file_path"
INDEX_COLUMN = "general/sim_idx"
LABEL_FILES = ["settings.csv", "settings_clean.csv", "labels.csv"]
ENCODING = "latin-1"  # never fails on any byte; the columns used here are plain ASCII and all other bytes are not changed


def relative_path(old_path, sim_idx, grid):
    """data/result<sim_idx>.csv; raises ValueError if old_path is not the result file of this simulation in this dataset"""
    new_path = f"data/result{sim_idx}.csv"
    if old_path != new_path and not old_path.replace("\\", "/").lower().endswith(f"/{grid}/{new_path}".lower()):
        raise ValueError(f"path {old_path!r} is not the result file of simulation {sim_idx} in dataset {grid}")
    return new_path


def parse_csv(raw):
    return list(csv.reader(io.StringIO(raw.decode(ENCODING), newline="")))


def convert_bytes(raw, grid):
    """returns the converted file content, the number of rows and the number of changed paths"""
    lines = raw.split(b"\n")
    header = next(csv.reader([lines[0].decode(ENCODING).rstrip("\r")]))
    path_col, index_col = header.index(PATH_COLUMN), header.index(INDEX_COLUMN)

    n_rows, n_changed = 0, 0
    for i, line in enumerate(lines[1:], start=1):
        if not line.strip():
            continue
        fields = next(csv.reader([line.decode(ENCODING).rstrip("\r")]))
        if len(fields) != len(header):
            raise ValueError(f"line {i + 1} has {len(fields)} columns, the header has {len(header)}")
        new_path = relative_path(fields[path_col], fields[index_col], grid)
        parts = line.split(b",", path_col + 1)
        if parts[path_col].decode(ENCODING) != fields[path_col]:
            raise ValueError(f"line {i + 1}: the path column cannot be located by commas (quoted field before it?)")
        n_rows += 1
        n_changed += new_path != fields[path_col]
        parts[path_col] = new_path.encode("ascii")
        lines[i] = b",".join(parts)
    return b"\n".join(lines), n_rows, n_changed


def verify(raw, new_raw, grid):
    """independent of the conversion: parses both versions and compares every cell"""
    old_rows, new_rows = parse_csv(raw), parse_csv(new_raw)
    if len(old_rows) != len(new_rows) or old_rows[0] != new_rows[0]:
        raise ValueError("number of rows or header changed")
    path_col, index_col = old_rows[0].index(PATH_COLUMN), old_rows[0].index(INDEX_COLUMN)
    for old, new in zip(old_rows[1:], new_rows[1:]):
        if new[:path_col] + new[path_col + 1:] != old[:path_col] + old[path_col + 1:]:
            raise ValueError(f"a value other than the path changed in simulation {old[index_col]}")
        if new[path_col] != relative_path(old[path_col], old[index_col], grid):
            raise ValueError(f"wrong path for simulation {old[index_col]}: {new[path_col]}")


def convert_file(path):
    grid = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(path))))
    with open(path, "rb") as f:
        raw = f.read()
    try:
        new_raw, n_rows, n_changed = convert_bytes(raw, grid)
        verify(raw, new_raw, grid)
    except ValueError as e:
        raise ValueError(f"{path}: {e}") from e
    return new_raw, n_rows, n_changed


def write_file(path, content):
    """written next to the file, read back and then moved over it, so an interruption cannot leave a partial file"""
    temporary = f"{path}.converting"
    with open(temporary, "wb") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    with open(temporary, "rb") as f:
        if f.read() != content:
            raise IOError(f"{temporary} differs from the converted content after writing, {path} was not changed")
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser(description="Make general/result_file_path in the labels relative to the dataset folder.")
    parser.add_argument("--dataset_path", type=str, required=True, help="dataset folder or folder with several datasets")
    parser.add_argument("--apply", action="store_true", help="write the converted files (without it, the files are only checked)")
    args = parser.parse_args()

    settings = sorted(glob.glob(os.path.join(args.dataset_path, "**", "labels", "settings.csv"), recursive=True))
    if not settings:
        raise FileNotFoundError(f"No labels/settings.csv found in {args.dataset_path}")
    files = [os.path.join(os.path.dirname(s), name) for s in settings for name in LABEL_FILES if os.path.exists(os.path.join(os.path.dirname(s), name))]

    # all files are checked before the first one is written
    conversions = []
    for path in files:
        new_raw, n_rows, n_changed = convert_file(path)
        conversions.append((path, new_raw, n_changed))
        print(f"{os.path.relpath(path, args.dataset_path)}: {n_rows} rows, {n_changed} paths to convert, {n_rows - n_changed} already relative")

    to_write = [(path, new_raw) for path, new_raw, n_changed in conversions if n_changed]
    if not args.apply:
        print(f"\nAll paths checked, {len(to_write)} of {len(files)} files would change. Nothing was written, use --apply to write them.")
        return
    for path, new_raw in to_write:
        write_file(path, new_raw)
    print(f"\nConverted {len(to_write)} of {len(files)} files.")


if __name__ == "__main__":
    main()
