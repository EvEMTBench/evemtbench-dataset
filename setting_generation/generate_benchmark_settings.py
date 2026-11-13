import math
import os
import pickle
import time

from util.create_grid_graph import create_graph_from_existing_grid
from util.pf_utils import nested_dicts_to_pd
from parameter_sampling.param_rand_sampling import EventSampler

evnt_sampler = EventSampler(None, None, None, None, None)

mv_switch_events = [evnt for evnt in evnt_sampler.mv_events if ("switch" in evnt and not 'trip' in evnt)]
mv_trip_events = [evnt for evnt in evnt_sampler.mv_events if 'trip' in evnt]
mv_fault_events = [evnt for evnt in evnt_sampler.mv_events if ("flt" in evnt and not ("incipient" in evnt or "hif" in evnt))]
mv_special_fault_events = [evnt for evnt in evnt_sampler.mv_events if ("incipient" in evnt or "hif" in evnt)]

hv_switch_events = [evnt for evnt in evnt_sampler.hv_events if ("switch" in evnt and not 'trip' in evnt)]
hv_trip_events = [evnt for evnt in evnt_sampler.hv_events if 'trip' in evnt]
hv_fault_events = [evnt for evnt in evnt_sampler.hv_events if ("flt" in evnt and not ("incipient" in evnt or "hif" in evnt))]
hv_special_fault_events = [evnt for evnt in evnt_sampler.hv_events if ("incipient" in evnt or "hif" in evnt)]

ehv_switch_events = [evnt for evnt in evnt_sampler.ehv_events if ("switch" in evnt and not 'trip' in evnt)]
ehv_trip_events = [evnt for evnt in evnt_sampler.ehv_events if 'trip' in evnt]
ehv_fault_events = [evnt for evnt in evnt_sampler.ehv_events if ("flt" in evnt and not ("incipient" in evnt or "hif" in evnt))]
ehv_special_fault_events = [evnt for evnt in evnt_sampler.ehv_events if ("incipient" in evnt or "hif" in evnt)]


def get_phase_indices(fault):
    # the phase selection does not apply to three-phase faults, which would otherwise be simulated three times identically
    return [0] if fault == "flt_3ph_shc" else [0, 1, 2]

def generate_benchmark_settings(pf, dataset_path, max_sims, vn, fn):
    user = pf.GetCurrentUser()
    active_project = pf.GetActiveProject()
    main_grid = active_project.GetContents('*Main*.ElmNet', 1)[0]
    all_lines = main_grid.GetContents('*Main*.ElmLne')
    main_busses = main_grid.GetContents('*Main*.ElmTerm')
    all_gens = main_grid.GetContents('*.ElmSym')
    all_ibrs = main_grid.GetContents('*IBR*.ElmVac')

    data_path = os.path.join(dataset_path, 'data')
    graph_path = os.path.join(dataset_path, 'graphs')

    grid_graph = create_graph_from_existing_grid(main_grid)
    pickle.dump(grid_graph, open(graph_path + '/graph_benchmark.pickle', 'wb'))

    exportObject = user.CreateObject('CompfdExport', 'Export')
    exportObject.SetAttribute('g_objects', [active_project])
    exportObject.g_file = str(os.path.join(graph_path, 'grid_benchmark.pfd')).replace('\\', '/')
    exportObject.Execute()
    exportObject.Delete()
    time.sleep(0.5)

    if vn == 20:
        benchmark_fault_events = mv_fault_events
        benchmark_special_fault_events = mv_special_fault_events
        benchmark_switch_events = mv_switch_events
        arc_tau = 0.3 * 1e-3
        arc_u0 = 800
        arc_r0 = 0.015
    elif vn == 110:
        benchmark_fault_events = hv_fault_events
        benchmark_special_fault_events = hv_special_fault_events
        benchmark_switch_events = hv_switch_events
        arc_tau = 0.8 * 1e-3
        arc_u0 = 4000
        arc_r0 = 0.15
    elif vn == 345:
        benchmark_fault_events = ehv_fault_events
        benchmark_special_fault_events = ehv_special_fault_events
        benchmark_switch_events = ehv_switch_events
        arc_tau = 0.8 * 1e-3
        arc_u0 = 8000
        arc_r0 = 0.4
    else:
        raise NotImplementedError

    resistances = [1, 10, 40]
    locations = [1, 20, 50, 80, 99]  # percentage of line length

    phase_select_2ph = ['ab', 'bc', 'ca']
    phase_select_1ph = ['a', 'b', 'c']

    n_fault_phase_combinations = sum(len(get_phase_indices(fault)) for fault in benchmark_fault_events)
    total_sims = (n_fault_phase_combinations * len(resistances) * len(all_lines) * len(locations) +
                  n_fault_phase_combinations * len(resistances) * len(main_busses) +

                  len(benchmark_switch_events) * len(main_busses) + len(all_gens) + len(all_ibrs) +

                  len(benchmark_special_fault_events) * (len(main_busses) + len(all_lines)) * 3
                  )

    # reduce the target lines so that we don't exceed max_sims
    if total_sims > max_sims:
        # Calculate how many lines to skip to meet the limit
        lines_to_skip = math.ceil((total_sims - max_sims) / (n_fault_phase_combinations * len(resistances) * len(locations)))
        every_nth_line = math.ceil(len(all_lines) / (len(all_lines) - lines_to_skip))
        if every_nth_line < 1:
            raise ValueError("Too many simulations to satisfy the maximum simulation limit")
        print(f"Total simulations requested: {total_sims}, Maximum number of simulations: {max_sims}, Considering every {every_nth_line} lines")
    else:
        every_nth_line = 1
        print(f"Total simulations requested: {total_sims}, Maximum number of simulations: {max_sims}")

    setting_dicts = []
    for fault in benchmark_fault_events:
        for resistance in resistances:
            for phase in get_phase_indices(fault):
                for line in all_lines[::every_nth_line]:
                    for location in locations:
                        setting_dict = {
                            "general": {
                                "result_file_path": os.path.join(data_path, f'result{len(setting_dicts)}.csv'),
                                "sim_idx": len(setting_dicts),
                                "vn": vn,
                                "fn": fn,
                                "grid_graph": "graph_benchmark.pickle",
                            },
                            "events": {
                                "event_type": fault,
                                "event_start": 1 + 0.1,
                                "event_target": line.loc_name,
                                "event_flt_target_line_location": location,
                                "event_flt_shc_resistance": resistance,
                                "event_flt_hif_resistance": None,
                                "event_phase_select_2ph": phase_select_2ph[phase],
                                "event_phase_select_1ph": phase_select_1ph[phase],
                                "event_iflt_duration": None,
                            },
                            "arc": {
                                "arc_tau": arc_tau,
                                "arc_u0": arc_u0,
                                "arc_r0": arc_r0,
                            },
                        }
                        setting_dicts.append(setting_dict)

                for bus in main_busses:
                    setting_dict = {
                        "general": {
                            "result_file_path": os.path.join(data_path, f'result{len(setting_dicts)}.csv'),
                            "sim_idx": len(setting_dicts),
                            "vn": vn,
                            "fn": fn,
                            "grid_graph": "graph_benchmark.pickle",
                        },
                        "events": {
                            "event_type": fault,
                            "event_start": 1 + 0.1,
                            "event_target": bus.loc_name,
                            "event_flt_target_line_location": None,
                            "event_flt_shc_resistance": resistance,
                            "event_flt_hif_resistance": None,
                            "event_phase_select_2ph": phase_select_2ph[phase],
                            "event_phase_select_1ph": phase_select_1ph[phase],
                            "event_iflt_duration": None,
                        },
                        "arc": {
                            "arc_tau": arc_tau,
                            "arc_u0": arc_u0,
                            "arc_r0": arc_r0,
                        },
                    }
                    setting_dicts.append(setting_dict)

    for event in benchmark_special_fault_events:
        for phase in [0, 1, 2]:
            for line in all_lines:
                setting_dict = {
                    "general": {
                        "result_file_path": os.path.join(data_path, f'result{len(setting_dicts)}.csv'),
                        "sim_idx": len(setting_dicts),
                        "vn": vn,
                        "fn": fn,
                        "grid_graph": "graph_benchmark.pickle",
                    },
                    "events": {
                        "event_type": event,
                        "event_start": 1 + 0.1,
                        "event_target": line.loc_name,
                        "event_flt_target_line_location": 50,
                        "event_flt_shc_resistance": 10,
                        "event_flt_hif_resistance": 5000,
                        "event_phase_select_2ph": None,
                        "event_phase_select_1ph": phase_select_1ph[phase],
                        "event_iflt_duration": 0.005,
                    },
                    "arc": {
                        "arc_tau": arc_tau,
                        "arc_u0": arc_u0,
                        "arc_r0": arc_r0,
                    },
                }
                setting_dicts.append(setting_dict)

            for bus in main_busses:
                setting_dict = {
                    "general": {
                        "result_file_path": os.path.join(data_path, f'result{len(setting_dicts)}.csv'),
                        "sim_idx": len(setting_dicts),
                        "vn": vn,
                        "fn": fn,
                        "grid_graph": "graph_benchmark.pickle",
                    },
                    "events": {
                        "event_type": event,
                        "event_start": 1 + 0.1,
                        "event_target": bus.loc_name,
                        "event_flt_target_line_location": None,
                        "event_flt_shc_resistance": 10,
                        "event_flt_hif_resistance": 5000,
                        "event_phase_select_2ph": None,
                        "event_phase_select_1ph": phase_select_1ph[phase],
                        "event_iflt_duration": 0.005,
                    },
                    "arc": {
                        "arc_tau": arc_tau,
                        "arc_u0": arc_u0,
                        "arc_r0": arc_r0,
                    },
                }
                setting_dicts.append(setting_dict)


    for event in benchmark_switch_events:
        for bus in main_busses:
            setting_dict = {
                "general": {
                    "result_file_path": os.path.join(data_path, f'result{len(setting_dicts)}.csv'),
                    "sim_idx": len(setting_dicts),
                    "vn": vn,
                    "fn": fn,
                    "grid_graph": "graph_benchmark.pickle",
                },
                "events": {
                    "event_type": event,
                    "event_start": 1 + 0.1,
                    "event_target": bus.loc_name,
                    "event_flt_target_line_location": None,
                    "event_flt_shc_resistance": None,
                    "event_flt_hif_resistance": None,
                    "event_phase_select_2ph": None,
                    "event_phase_select_1ph": None,
                    "event_iflt_arc_on": False,
                    "event_iflt_duration": None,
                },
            }
            setting_dicts.append(setting_dict)

    for generator in all_gens:
        if generator.typ_id.ugn == vn:
            # skip grid equivalents to avoid instability.
            continue

        setting_dict = {
            "general": {
                "result_file_path": os.path.join(data_path, f'result{len(setting_dicts)}.csv'),
                "sim_idx": len(setting_dicts),
                "vn": vn,
                "fn": fn,
                "grid_graph": "graph_benchmark.pickle",
            },
            "events": {
                "event_type": "switch_gen_trip",
                "event_start": 1 + 0.1,
                "event_target": generator.bus1.cterm.GetNextHVBus().loc_name,
                "event_flt_target_line_location": None,
                "event_flt_shc_resistance": None,
                "event_flt_hif_resistance": None,
                "event_phase_select_2ph": None,
                "event_phase_select_1ph": None,
                "event_iflt_arc_on": False,
                "event_iflt_duration": None,
            },
        }
        setting_dicts.append(setting_dict)


    for ibr in all_ibrs:
        setting_dict = {
            "general": {
                "result_file_path": os.path.join(data_path, f'result{len(setting_dicts)}.csv'),
                "sim_idx": len(setting_dicts),
                "vn": vn,
                "fn": fn,
                "grid_graph": "graph_benchmark.pickle",
            },
            "events": {
                "event_type": "switch_ibr_trip",
                "event_start": 1 + 0.1,
                "event_target": ibr.p_uctrl.p_cub.cterm.loc_name,
                "event_flt_target_line_location": None,
                "event_flt_shc_resistance": None,
                "event_flt_hif_resistance": None,
                "event_phase_select_2ph": None,
                "event_phase_select_1ph": None,
                "event_iflt_arc_on": False,
                "event_iflt_duration": None,
            },
        }
        setting_dicts.append(setting_dict)

    setting_df = nested_dicts_to_pd(setting_dicts)
    return setting_df