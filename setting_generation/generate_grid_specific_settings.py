import os
import pickle
import time

from tqdm import tqdm

from parameter_sampling.param_rand_sampling import *
from util.create_grid_graph import create_graph_from_existing_grid
from util.pf_utils import nested_dicts_to_pd


def generate_grid_specific_settings(pf, dataset_path, max_sims, vn, fn, grid_number=0, debug=False):
    # we want to randomize: Event Parameters, Load Parameters (and therefore generator parameters), Petersen Coil Parameters

    active_project = pf.GetActiveProject()
    main_grid = active_project.GetContents('*Main*.ElmNet', 1)[0]

    all_loads = main_grid.GetContents('*.ElmLod')
    all_generators = main_grid.GetContents('*.ElmSym')
    all_ibrs = main_grid.GetContents('*IBR*.ElmVac')

    data_path = os.path.join(dataset_path, 'data')
    graph_path = os.path.join(dataset_path, 'graphs')

    grid_graph = create_graph_from_existing_grid(main_grid)
    pickle.dump(grid_graph, open(graph_path + f'/graph_grid{grid_number}.pickle', 'wb'))

    user = pf.GetCurrentUser()
    active_project = pf.GetActiveProject()

    exportObject = user.CreateObject('CompfdExport', 'Export')
    exportObject.SetAttribute('g_objects', [active_project])
    exportObject.g_file = str(os.path.join(graph_path, f'grid{grid_number}.pfd')).replace('\\', '/')
    exportObject.Execute()
    exportObject.Delete()
    time.sleep(0.5)

    event_sampler = EventSampler(pf, vn, fn, main_grid, debug)
    arc_sampler = ArcSampler(pf, vn, fn)
    grounding_sampler = GroundingSampler(pf, vn, fn)
    capacitance_sampler = CapacitanceSampler(pf, vn, fn)
    line_sampler = LineSampler(pf, vn, fn)
    switch_trafo_sampler = SwitchTrafoSampler(pf, vn, fn)
    load_sampler = LoadSampler(pf, vn, fn)
    ext_grid_sampler = ExternalGridSampler(pf, vn, fn)

    if vn <= 110:
        motor_sampler = MotorSampler(pf, vn, fn)

    if vn >= 110:
        sym_sampler = SynchronousMachineSampler(pf, vn, fn)

    setting_dicts = []
    print("Creating Simulation Settings")
    for i in tqdm(range(max_sims)):
        result_file_path = os.path.join(data_path, f'result{i + grid_number}.csv')
        setting_dict = {}
        # Add general settings
        setting_dict["general"] = {
            "result_file_path": result_file_path,
            "sim_idx": i + grid_number,
            "vn": vn,
            "fn": fn,
            "grid_graph": f"graph_grid{grid_number}.pickle"
        }

        # Add event settings
        setting_dict["events"] = {}
        setting_dict["events"]["event_type"] = event_sampler.get_event_type()
        setting_dict["events"]["event_start"] = event_sampler.get_event_start()

        event_target = event_sampler.get_target(setting_dict["events"]["event_type"])

        if event_target.typ_id is not None:
            if event_target.typ_id.GetClassName() == 'TypCabsys' or (event_target.typ_id.GetClassName() == 'TypLne' and event_target.typ_id.cohl_ == 0):
                is_cable = True
            else:
                is_cable = False
        else:
            is_cable = False


        setting_dict["events"]["event_target"] = event_target.loc_name
        setting_dict["events"]["event_flt_target_line_location"] = event_sampler.get_flt_target_line_location()
        setting_dict["events"]["event_flt_shc_resistance"] = event_sampler.get_shc_resistance()
        setting_dict["events"]["event_flt_hif_resistance"] = event_sampler.get_hif_resistance()
        setting_dict["events"]["event_phase_select_2ph"] = event_sampler.get_phase_2ph()
        setting_dict["events"]["event_phase_select_1ph"] = event_sampler.get_phase_1ph()
        setting_dict["events"]["event_iflt_duration"] = event_sampler.get_iflt_duration()

        setting_dict["arc"] = {}
        setting_dict["arc"]["arc_tau"] = arc_sampler.get_tau(is_cable)
        setting_dict["arc"]["arc_u0"] = arc_sampler.get_u0(is_cable)
        setting_dict["arc"]["arc_r0"] = arc_sampler.get_r0(is_cable)

        # Add grounding settings
        setting_dict["grounding"] = {}
        setting_dict["grounding"]["grnd_type"] = grounding_sampler.get_grnd_type()
        setting_dict["grounding"]["coil_tuning"] = grounding_sampler.get_coil_tuning()
        setting_dict["grounding"]["solid_ground_resistance"] = grounding_sampler.get_solid_resistance()
        setting_dict["grounding"]["resistive_ground_resistance"] = grounding_sampler.get_resistive_ground_resistance()
        setting_dict["grounding"]["parasitic_resistance_percentage"] = grounding_sampler.get_parasitic_resistance_percentage()

        # Add switch capacitance settings
        setting_dict["cap_switch"] = {}
        setting_dict["cap_switch"]["cap_power"] = capacitance_sampler.get_cap_power()

        setting_dict["ohl_switch"] = {}
        setting_dict["ohl_switch"]["ohl_length"] = line_sampler.get_length(is_cable=False)
        setting_dict["ohl_switch"]["ohl_type"] = line_sampler.get_line_typ(is_cable=False).loc_name

        setting_dict["cable_switch"] = {}
        setting_dict["cable_switch"]["cable_length"] = line_sampler.get_length(is_cable=True)
        setting_dict["cable_switch"]["cable_type"] = line_sampler.get_line_typ(is_cable=True).loc_name

        setting_dict["switch_trafo_to_lv_type"] = switch_trafo_sampler.get_trafo_to_lv().loc_name


        if vn <= 110:
            setting_dict["switch_trafo_to_hv_type"] = switch_trafo_sampler.get_trafo_to_hv().loc_name

            setting_dict["motor_start"] = {}
            setting_dict["motor_start"]["motor_type"] = motor_sampler.get_motor_type().loc_name
            setting_dict["motor_start"]["motor_trafo_type"] = motor_sampler.get_motor_trafo_type().loc_name

        setting_dict["loads"] = {}

        psum_loads = 0
        for load in all_loads:
            ld_name = load.loc_name
            scaler = load_sampler.get_load_scaling_factor()
            load_p = load.plini * scaler
            load_q = load.qlini * scaler

            setting_dict["loads"][ld_name] = {}
            setting_dict["loads"][ld_name]["load_p"] = load_p
            setting_dict["loads"][ld_name]["load_q"] = load_q
            psum_loads += load_p

        if vn >= 110:
            dispatchable_generators = get_dispatchable_generators(all_generators)
            if dispatchable_generators:
                # same dispatch as in build_pf_grid (IBR setpoints are not varied per simulation, but count as local generation)
                ssum_gens = get_generation_capacity(all_generators, all_ibrs)
                locality_factor = load_sampler.get_locality_factor()
                power_share = get_generation_share(psum_loads, ssum_gens, locality_factor)
                setting_dict["dispatch"] = {"locality_factor": locality_factor, "power_share": power_share}
                setting_dict["gens"] = {}
                for gen in dispatchable_generators:
                    gen_name = gen.loc_name
                    setting_dict["gens"][gen_name] = {}
                    setting_dict["gens"][gen_name]["pgen"] = gen.typ_id.sgn * power_share
                    setting_dict["gens"][gen_name]["usetp"] = sym_sampler.get_usetp()

        setting_dict['ExtGrid'] = {}
        setting_dict['ExtGrid']['usetp'] = ext_grid_sampler.get_usetp()
        setting_dict['ExtGrid']['phiini'] = ext_grid_sampler.get_phiini()

        setting_dicts.append(setting_dict)


    setting_df = nested_dicts_to_pd(setting_dicts)

    return setting_df
