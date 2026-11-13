import argparse  # Parser for command-line options, arguments and sub-commands
import os  # Miscellaneous operating system interfaces

import pandas as pd
from tqdm import tqdm

from util.post_processing import post_process_dataset
from setting_generation.generate_dynamic_grid_settings import generate_grid_topology
from setting_generation.generate_grid_specific_settings import generate_grid_specific_settings

from setting_generation.generate_benchmark_settings import generate_benchmark_settings
from util.pf_utils import reset_project, create_replica_studycase, folder_setup, check_pf_file, get_grid_params

import powerfactory  # the Python folder of PowerFactory must be on PYTHONPATH (set by create_datasets.py)


def create_and_execute_const_topology_sims(pf, dataset_type, dataset_path, sim_file_path, chunk_size, max_simulations, debug):

    vn, fn = get_grid_params(sim_file_path)

    if dataset_type == 'benchmark':
        setting_df = generate_benchmark_settings(pf, dataset_path, max_simulations, vn, fn)
    elif dataset_type == 'adapt_grid':
        setting_df = generate_grid_specific_settings(pf, dataset_path, max_simulations, vn, fn, debug=debug)
    else:
        raise NotImplementedError

    label_path = os.path.join(dataset_path, 'labels')
    setting_path = os.path.join(label_path, 'settings.csv')
    setting_df.to_csv(setting_path)

    for chunk_start in tqdm(range(0, len(setting_df), chunk_size)):
        sc_main, sc_folder = reset_project(pf, sim_file_path)
        ta_handle = sc_folder.GetContents('*Task Automation.ComTasks', 1)[0]
        ta_handle.butRemCases = 1  # Delete all previous Studycases from Taskautomation
        ta_handle.transDbChanges = 1  # Transfer only result files back to the main.

        for sc_idx in range(chunk_start, min(chunk_start + chunk_size, len(setting_df))):
            replica_sc = create_replica_studycase(sc_idx, sc_folder, sc_main, setting_path)
            ta_handle.AppendStudyCase(replica_sc)
            parallel_sim_handler_script = replica_sc.GetContents('parallel_sim_handler.ComPython')[0]
            ta_handle.AppendCommand(parallel_sim_handler_script, 0)

        ta_handle.Execute()


def create_and_execute_dyn_topology_sims(pf, dataset_path, sim_file_path, chunk_size, max_simulations, debug, dtemt=1e-5, fs_export=9600):
    vn, fn = get_grid_params(sim_file_path)

    setting_df = pd.DataFrame()
    for chunk_start in tqdm(range(0, max_simulations, chunk_size)):
        while True:
            sc_main, sc_folder = reset_project(pf, sim_file_path)
            grid_okay = generate_grid_topology(pf, vn, fn, debug, dtemt, fs_export)
            if grid_okay:
                break
            else:
                print("Generated Grid infeasible, trying again...")

        n_sims_chunk = min(chunk_size, max_simulations - chunk_start)  # the last chunk can be smaller
        setting_df_part = generate_grid_specific_settings(pf, dataset_path, n_sims_chunk, vn, fn, chunk_start, debug=debug)
        setting_df = pd.concat([setting_df, setting_df_part], ignore_index=True)

        label_path = os.path.join(dataset_path, 'labels')
        setting_path = os.path.join(label_path, 'settings.csv')
        setting_df.to_csv(setting_path)

        ta_handle = sc_folder.GetContents('*Task Automation.ComTasks', 1)[0]
        ta_handle.butRemCases = 1  # Delete all previous Studycases from Taskautomation
        ta_handle.transDbChanges = 1  # Transfer only result files back to the main.

        for sc_idx in range(chunk_start, min(chunk_start + chunk_size, max_simulations)):
            replica_sc = create_replica_studycase(sc_idx, sc_folder, sc_main, setting_path)
            ta_handle.AppendStudyCase(replica_sc)
            parallel_sim_handler_script = replica_sc.GetContents('parallel_sim_handler.ComPython')[0]
            ta_handle.AppendCommand(parallel_sim_handler_script, 0)

        ta_handle.Execute()

def create_and_execute_simulations(pf, dataset_type, dataset_path, sim_file_path, chunk_size, max_simulations, debug, dtemt=1e-5, fs_export=9600):
    # benchmark and adapt_grid use the step size and export rate stored in the model by pf_prepare_models.py
    if dataset_type == 'benchmark' or dataset_type == 'adapt_grid':
        create_and_execute_const_topology_sims(pf, dataset_type, dataset_path, sim_file_path, chunk_size, max_simulations, debug)
    elif dataset_type == 'multi_grid':
        create_and_execute_dyn_topology_sims(pf, dataset_path, sim_file_path, chunk_size, max_simulations, debug, dtemt, fs_export)
    else:
        raise NotImplementedError


def main():
    # Point on Wave Data of Grid Events based on Simulations
    parser = argparse.ArgumentParser(description='Process some parameters.')
    parser.add_argument('--dataset_path',                                   type=str, required=True)
    parser.add_argument('--max_simulations',    default=100,                type=int, required=False)
    parser.add_argument('--sim_file_path',                                  type=str, required=True)
    parser.add_argument('--dataset_type',       default='multi_grid',       type=str, required=False, choices=['benchmark', 'adapt_grid', 'multi_grid'])
    parser.add_argument('--debug',                                          type=str, required=True)
    parser.add_argument('--showpf',             default="True",             type=str, required=False)
    parser.add_argument('--chunk_size',         default=10,                 type=int, required=False)
    parser.add_argument('--dtemt',              default=1e-5,               type=float, required=False)
    parser.add_argument('--fs_export',          default=9600,               type=float, required=False)
    parser.add_argument('--n_target',           default=0,                  type=int, required=False)  # 0: keep all retained simulations
    args = parser.parse_args()

    sim_file_name = os.path.basename(args.sim_file_path)
    print(sim_file_name)

    pf = powerfactory.GetApplicationExt()

    if args.showpf == "True":
        pf.Show()
    if args.debug == "True":
        args.debug = True
    else:
        args.debug = False

    folder_setup(args.dataset_path)

    reset_project(pf, args.sim_file_path)
    check_pf_file(pf, args.debug, dtemt=args.dtemt, fs_export=args.fs_export)
    create_and_execute_simulations(pf,
                                   args.dataset_type,
                                   args.dataset_path,
                                   args.sim_file_path,
                                   int(args.chunk_size),
                                   int(args.max_simulations),
                                   args.debug,
                                   args.dtemt,
                                   args.fs_export)

    if args.dataset_type == 'benchmark' and args.n_target:
        print('n_target is ignored for benchmark datasets, all retained simulations of the sweep are kept.')
        args.n_target = 0
    post_process_dataset(args.dataset_path, n_target=args.n_target)

    print('Script Finished')


if __name__ == '__main__':
    main()