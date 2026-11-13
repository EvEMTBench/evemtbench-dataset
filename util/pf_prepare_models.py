"""
Prepares the grid models in the model folder (default: models/ of the repository) for the simulations and exports them
back to the same files: measurements, result export, simulation settings and the paths of this machine (IBR controller
FMU, script file of the simulation handler util/parallel_sim_handler.py). Run once on every machine before generating
datasets (create_datasets.py does this in its step "models").
Usage: python util/pf_prepare_models.py --debug False [--model_dir <folder>] [--dtemt 1e-5] [--fs_export 9600]
(the repository and the Python folder of PowerFactory must be on PYTHONPATH)
"""
import argparse
import math
import os
import time

from util.pf_utils import check_pf_file, get_pf_lib

import powerfactory

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HANDLER_SCRIPT = os.path.join(REPO_DIR, 'util', 'parallel_sim_handler.py')  # executed by PowerFactory for every simulation


def prepare_model(pf, debug=False, dtemt=1e-5, fs_export=9600):
    """
    Prepare the PowerFactory model for simulation.
    This includes deleting existing CTs, VTs, results, and exports.
    dtemt is the EMT integration step size in s, fs_export the rate of the exported results in Hz.
    """
    active_project = pf.GetActiveProject()
    main_grid = active_project.GetContents('*Main*.ElmNet', 1)[0]
    sc_main = active_project.GetContents('MainStudyCase.IntCase', 1)[0]
    all_lines = main_grid.GetContents('*.ElmLne')
    main_busses = main_grid.GetContents('*Main*.ElmTerm')


    # =========================== Delete Exisiting CTs, VTs, Results, and Exports =========================== #
    existing_ctvts = active_project.GetContents('*pex_*.StaCombi', 1)
    for existing_ctvt in existing_ctvts:
        existing_ctvt.Delete()

    results = active_project.GetContents('*.ElmRes', 1)
    for res in results:
        res.Delete()

    exports = active_project.GetContents('*.ComRes', 1)
    for exp in exports:
        exp.Delete()

    # =========================== Create CTs and VTs =========================== #
    for bus in main_busses:
        cubicles = bus.GetConnectedCubicles(1)  # 1: ignore switch states (PowerFactory API takes no keyword arguments)
        for cubic in cubicles:
            assert len(cubic.GetConnections(0)) == 2

            cubic_bus = cubic.cterm  # Previous component connected to the cubicle
            cubic_branch = cubic.obj_id  # Next component connected to the cubicle
            cubic.CreateObject('StaCombi', 'pex_' + str(cubic_bus.loc_name) + '_' + str(cubic_branch.loc_name))


    # =========================== Create Export ========================= #
    export_list = ['c:Isec:A', 'c:Isec:B', 'c:Isec:C', 'c:Usec:A', 'c:Usec:B', 'c:Usec:C']

    evemt_result = sc_main.CreateObject('ElmRes', 'EvemtResult')
    existing_ctvts = active_project.GetContents('*pex*.StaCombi', 1)
    for ctvt in existing_ctvts:
        for param in export_list:
            evemt_result.AddVariable(ctvt, param)
    inc = sc_main.GetContents('*.ComInc')[0]
    inc.p_resvar = evemt_result

    simscan = sc_main.GetContents('*WarnScan.ScnVar', 1)[0]
    simscan.simscanobj = inc.p_resvar

    # Create export object
    main_export = sc_main.CreateObject('ComRes', 'ExportEvemt')
    main_export.pResult = evemt_result

    main_export.SetAttribute("iopt_exp", 6)  # csv
    main_export.SetAttribute("numberFormat", 0)  # decimal
    main_export.SetAttribute("numberPrecisionFixed", 12)
    main_export.SetAttribute("iopt_sep", False)
    main_export.SetAttribute("col_Sep", ",")
    main_export.SetAttribute("dec_Sep", ".")


    main_export.SetAttribute("iopt_csel", 0)
    main_export.SetAttribute("iopt_tsel", True)
    if debug:
        main_export.SetAttribute("from", 0.0)
    else:
        main_export.SetAttribute("from", 1.0)

    main_export.SetAttribute("to", 1.5)
    main_export.ciopt_head = 1
    main_export.f_name = 'default_export.csv'

    # The study case command parallel_sim_handler.ComPython refers to a remote script in the library of the project
    # (Library/Scripts/parallel_sim_handler_benchmark.ComPython) that runs an external script file. Point every
    # parallel_sim_handler script of the project to util/parallel_sim_handler.py of this repository.
    for handler in active_project.GetContents('*parallel_sim_handler*.ComPython', 1):
        handler.SetAttribute('filePath', HANDLER_SCRIPT)

    sc_folder = sc_main.GetParent()
    ta_handle = sc_folder.GetContents('*Task Automation.ComTasks', 1)

    if len(ta_handle) > 0:
        for i in ta_handle:
            i.Delete()

    ta_handle = sc_folder.CreateObject('ComTasks', 'Task Automation')
    ta_handle.iEnableParal = True
    ta_handle.parMethod = 0
    ta_handle.transDbChanges = 1  # Transfer only result files back to the main.

    events = inc.p_event

    if events is not None:
        for event in events.GetContents():
            event.Delete()

    # =========================== Set Sim Parameters ========================= #
    input_options = active_project.GetContents("*Settings Serial Reactance*", 1)[0]
    input_options.iopt_uz = "rx"

    inc = sc_main.GetContents('*.ComInc')[0]
    ldf = sc_main.GetContents('*.ComLdf')[0]
    sim = sc_main.GetContents('*.ComSim')[0]

    ldf.iopt_net = 1
    ldf.iopt_plim = True
    ldf.iopt_lim = True
    ldf.iopt_pq = True
    ldf.iopt_apdist = 0
    ldf.iopt_iPbalancing = 0
    ldf.iopt_pq = True

    # Set simulation parameters
    inc.iopt_sim = 'ins'
    inc.dtemt = dtemt
    inc.tstart = 0.0
    inc.iopt_sync = True  # enforced synchronisation: results are calculated at every syncperiod
    inc.syncperiod = 1/fs_export
    inc.ciopt_sample = 2  # record results only at the synchronised points in time
    if debug:
        sim.tstop = 0.1
    else:
        sim.tstop = 1.5
    pf.WriteChangesToDb()


def prepare_ibr_model(pf, model_dir):
    user = pf.GetCurrentUser()
    parent_lib = get_pf_lib(user, "CustomTypeLib")

    ibr_lib = get_pf_lib(parent_lib, "IBRModel")
    fmu_model = ibr_lib.GetContents("FMUIBRController.TypMdl", 1)[0]
    fmu_model.cfilePath = str(os.path.normpath(os.path.join(model_dir, "IBRviaFMU", "IBR_Control_Only.fmu")))



def main(pf, debug, dtemt=1e-5, fs_export=9600, model_dir=os.path.join(REPO_DIR, 'models')):
    model_dir = os.path.abspath(model_dir)

    prepare_ibr_model(pf, model_dir)

    # list all pfd files in the models folder
    model_files = [f for f in os.listdir(model_dir) if (f.endswith('.pfd') and 'Lib' not in f)]

    for model_file in model_files:
        print(model_file)
        project_name = os.path.basename(model_file).split('.')[0] + '.IntPrj'

        user_folder = pf.GetCurrentUser()
        projects = user_folder.GetContents(project_name)

        for project in projects:
            project.Deactivate()
            project.Delete()

        import_obj = user_folder.CreateObject('CompfdImport', 'Import')
        import_path = os.path.join(model_dir, model_file)
        import_obj.SetAttribute("e:g_file", import_path)
        import_obj.g_target = user_folder
        import_obj.Execute()
        import_obj.Delete()
        pf.ClearRecycleBin()
        pf.ActivateProject(project_name)

        prepare_model(pf, debug=debug, dtemt=dtemt, fs_export=fs_export)

        check_pf_file(pf, debug, dtemt=dtemt, fs_export=fs_export)

        user = pf.GetCurrentUser()
        active_project = pf.GetActiveProject()

        exportObject = user.CreateObject('CompfdExport', 'Export')
        exportObject.SetAttribute('g_objects', [active_project])
        exportObject.g_file = os.path.join(model_dir, active_project.loc_name + '.pfd')
        exportObject.Execute()
        exportObject.Delete()

        time.sleep(0.5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process some parameters.')
    parser.add_argument('--debug',              default="False",                                                               type=str, required=True)
    parser.add_argument('--dtemt',              default=1e-5,                                                                  type=float, required=False)
    parser.add_argument('--fs_export',          default=9600,                                                                  type=float, required=False)
    parser.add_argument('--model_dir',          default=os.path.join(REPO_DIR, 'models'),                                      type=str, required=False)
    args = parser.parse_args()

    if args.debug == "True":
        args.debug = True
    else:
        args.debug = False

    pf = powerfactory.GetApplication()
    main(pf, args.debug, args.dtemt, args.fs_export, args.model_dir)
