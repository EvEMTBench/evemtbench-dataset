"""
Splits the multigrid and adapt_grid datasets into train, validation and test sets (80/10/10). Multigrid datasets are
split by topology (general/grid_graph), so all simulations of a topology are in the same set. Adapt_grid datasets are
split randomly by simulation. Writes one file per dataset to OUTPUT_PATH, <subset>-<grid>.csv with the columns sim_idx
(as in labels/labels.csv; the result file is data/result<sim_idx>.csv) and split (train, val or test).
Usage: python split_datasets.py --dataset_path <folder with the extracted datasets (multi_grid/<grid>, adapt_grid/<grid>)>
Requires pandas and scikit-learn.
"""
import argparse
import os

import pandas as pd
from sklearn.model_selection import train_test_split

parser = argparse.ArgumentParser(description="Write the train / val / test splits of the multigrid and adapt_grid datasets.")
parser.add_argument("--dataset_path", required=True, help="folder with the extracted datasets (multi_grid/<grid>, adapt_grid/<grid>)")
DATASET_PATH = parser.parse_args().dataset_path
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "splits")
DATASETS = ["multi_grid/Template20kV", "multi_grid/Template110kV", "multi_grid/Template345kV", "adapt_grid/CigreMVGrid",
            "adapt_grid/DoubleLine", "adapt_grid/IEEE39BusSystem", "adapt_grid/TestGrid110kV"]
SEED = 0

os.makedirs(OUTPUT_PATH, exist_ok=True)
for dataset in DATASETS:
    labels = pd.read_csv(os.path.join(DATASET_PATH, dataset, "labels", "labels.csv"), usecols=["general/sim_idx", "general/grid_graph"])

    # the units that are split: topologies (multigrid) or single simulations (adapt_grid)
    units = labels["general/grid_graph"] if dataset.startswith("multi_grid") else labels["general/sim_idx"]
    train, rest = train_test_split(units.unique(), test_size=0.2, random_state=SEED)
    val, test = train_test_split(rest, test_size=0.5, random_state=SEED)

    split = pd.DataFrame({"sim_idx": labels["general/sim_idx"], "split": "train"})
    split.loc[units.isin(val), "split"] = "val"
    split.loc[units.isin(test), "split"] = "test"
    split.to_csv(os.path.join(OUTPUT_PATH, dataset.replace("/", "-") + ".csv"), index=False)
    print(f"{dataset}: {len(train)}/{len(val)}/{len(test)} {'topologies' if dataset.startswith('multi_grid') else 'simulations'}, "
          f"simulations per set: {split['split'].value_counts().to_dict()}")
