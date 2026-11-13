import math
import os

from flatten_json import flatten, unflatten_list
import pandas as pd
import networkx as nx


def get_grid_params(sim_file_path):
    sim_file_name = os.path.basename(sim_file_path)

    if sim_file_name == "CigreMVGrid.pfd" or sim_file_name == "Template20kV.pfd":
        vn = 20
        fn = 50
    elif sim_file_name == "DoubleLine.pfd" or sim_file_name == "TestGrid110kV.pfd" or sim_file_name == "Template110kV.pfd":
        vn = 110
        fn = 50
    elif sim_file_name == "IEEE39BusSystem.pfd" or sim_file_name == "Template345kV.pfd":
        vn = 345
        fn = 60
    else:
        raise NotImplementedError
    return vn, fn


def nested_dicts_to_pd(data):
    flat_data = [flatten(item, '/') for item in data]
    df = pd.DataFrame(flat_data)
    return df


def get_pf_lib(parent_folder, child_name):
    try:
        ret_lib = parent_folder.GetContents(f"*{child_name}*")[0]
    except IndexError:
        parent_folder.CreateObject("IntFolder", child_name)
        ret_lib = parent_folder.GetContents(f"*{child_name}*")[0]
        ret_lib.iopt_typ = 1
    try:
        ret_lib.Activate()
    except:
        pass

    return ret_lib



def reset_project(pf, sim_file_path):
    """
    Function deletes the PowerFactory project and re-imports it, to avoid powerfactory using too much memory.
    """
    project_name = os.path.basename(sim_file_path).split('.')[0] + '.IntPrj'

    user_folder = pf.GetCurrentUser()
    projects = user_folder.GetContents(project_name)

    for project in projects:
        project.Deactivate()
        project.Delete()

    imports = user_folder.GetContents("*.CompfdImport")
    for i in imports:
        i.Delete()
        print(f"Deleted Import - Unclear why it was still there.")

    import_obj = user_folder.CreateObject('CompfdImport', 'Import')
    import_path = os.path.abspath(sim_file_path)
    import_obj.SetAttribute("e:g_file", import_path)
    import_obj.g_target = user_folder
    import_obj.Execute()
    import_obj.Delete()
    pf.ClearRecycleBin()
    pf.ActivateProject(project_name)

    active_project = pf.GetActiveProject()
    sc_main = active_project.GetContents('MainStudyCase.IntCase', 1)[0]
    sc_folder = sc_main.GetParent()

    main_grid = active_project.GetContents('*Main*.ElmNet', 1)[0]
    custom_type_lib_local = main_grid.CreateObject("IntFolder", "CustomTypeLib")
    custom_type_lib_local.iopt_typ = 1

    custom_type_lib = user_folder.GetContents(f"*CustomTypeLib*")[0]
    sub_libs = custom_type_lib.GetContents("*")
    for sub_lib in sub_libs:
        if not "Exciter" in str(sub_lib):
            custom_type_lib_local.AddCopy(sub_lib)

    inc = sc_main.GetContents('*.ComInc')[0]
    inc.Execute()

    return sc_main, sc_folder


def create_replica_studycase(sc_idx, sc_folder, sc_main, setting_path):
    """
    The function will create the actual powerfactory studycases (replica of main studycase) and write the replica
    settings into the description of the studycase, so they can be applied by the precalculation script.
    :param replica:
    :param replicanumber:
    :param conf:
    """
    replica_sc = sc_folder.AddCopy(sc_main, 'sc_replica' + str(sc_idx))
    parallel_sim_handler = replica_sc.GetContents('*parallel_sim_handler.ComPython', 1)[0]
    parallel_sim_handler.SetAttribute('IntExpr', [str(setting_path).replace('\\', '/'), str(sc_idx)])

    return replica_sc


def folder_setup(dataset_path):
    """
    Creates the necessary folders for the dataset and prepares the base model for simulation as necessary
    :return:
    """
    data_path = os.path.join(dataset_path, 'data')
    label_path = os.path.join(dataset_path, 'labels')
    graph_path = os.path.join(dataset_path, 'graphs')
    os.makedirs(data_path, exist_ok=True)
    os.makedirs(label_path, exist_ok=True)
    os.makedirs(graph_path, exist_ok=True)


def check_pf_file(pf, debug, dtemt=1e-5, fs_export=9600):
    active_project = pf.GetActiveProject()
    assert active_project is not None, 'Import failed'
    assert len(active_project.GetContents('MainStudyCase.IntCase', 1)) > 0, 'No main studycase.'
    assert len(active_project.GetContents('*Main*.ElmNet', 1)) > 0, 'No main grid.'

    input_options = active_project.GetContents("*Settings Serial Reactance*", 1)[0]
    assert input_options.iopt_uz == "rx"

    sc_main = active_project.GetContents('MainStudyCase.IntCase', 1)[0]
    study_case_folder = sc_main.GetParent()
    ldf = sc_main.GetContents('*.ComLdf')[0]
    inc = sc_main.GetContents('*.ComInc')[0]
    inc_result = inc.Execute()
    sim = sc_main.GetContents('*.ComSim')[0]

    assert (inc_result == 0 or inc_result == 1), 'Simulation not setup correct.'
    assert sim is not None, 'Simulation not setup correct.'

    # check correct sim setup
    assert inc.iopt_sim == 'ins', 'Simulation not setup correct.'
    assert math.isclose(inc.dtemt, dtemt, rel_tol=1e-5), 'Simulation not setup correct.'  # default 10 us
    assert math.isclose(inc.tstart, 0.0, rel_tol=1e-5), 'Simulation not setup correct.'  # for initial transients to settle
    assert inc.iopt_sync == True, 'Simulation not setup correct.'
    assert math.isclose(inc.syncperiod, 1/fs_export, rel_tol=1e-3), 'Simulation not setup correct.'  # default 9600 Hz
    assert inc.ciopt_sample == 2, 'Simulation not setup correct.'
    assert (inc.iopt_simscn == True), 'Simulation not setup correct.'
    assert len(sc_main.GetContents('*WarnScan.ScnVar', 1)) > 0, 'Simulation not setup correct.'
    assert len(sc_main.GetContents('*.IntScn')) > 0, 'Simulation not setup correct.'

    if debug:
        assert math.isclose(sim.tstop, 0.1, rel_tol=1e-5), 'Simulation not setup correct.'
    else:
        assert math.isclose(sim.tstop, 1.5, rel_tol=1e-5), 'Simulation not setup correct.'
    handler = sc_main.GetContents('*parallel_sim_handler.ComPython', 1)[0]
    assert handler is not None, 'Simulation not setup correct.'
    script = handler.GetAttribute('script_id') if handler.GetAttribute('isRemoteScriptSet') else handler
    assert os.path.isfile(script.GetAttribute('filePath')), \
        f"Script file {script.GetAttribute('filePath')} of {script.loc_name} not found: run util/pf_prepare_models.py on this machine"
    assert study_case_folder.GetContents('*Task Automation.ComTasks', 1)[0] is not None, 'Simulation not setup correct.'

    assert (ldf.iopt_net == 1), 'Simulation not setup correct.'

    print('Simulation setup and check successful')
