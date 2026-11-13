import csv
import math
import traceback
import os
import pandas as pd
from flatten_json import unflatten_list

import powerfactory

CLEANUP_DICT = {
    "required": False,
    "line_orig_length": None,
    "line_bus1": None,
    "line_bus2": None,

    "line_main": None,
    "line_split": None,
    "fault_term": None
}


# ========================================== UTIL FUNCTIONS ========================================== #
def csv_to_nested_dicts(filepath, idx):
    """
    A CSV file is better for storing the simulation settings than a JSON file because it allows for easy
    comparison of different simulations. However, the nested dictionary structure is more convenient for
    accessing the parameters. This function converts the CSV to a nested dictionary.
    """
    df = pd.read_csv(filepath, index_col="general/sim_idx")
    setting_dict = unflatten_list(df.loc[idx].to_dict(), '/')

    return setting_dict


def write_sim_status(setting_file_path, sc_idx, status, message=""):
    """
    Writes the outcome of one simulation to <labels>/status/sim_status_<sc_idx>.csv. One file per simulation avoids
    concurrent writes from the parallel task automation processes; post-processing merges them into sim_status.csv.
    Must never raise, so that logging cannot change the outcome of a simulation.
    """
    try:
        status_dir = os.path.join(os.path.dirname(str(setting_file_path)), 'status')
        os.makedirs(status_dir, exist_ok=True)
        with open(os.path.join(status_dir, f'sim_status_{sc_idx}.csv'), 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['sim_idx', 'sim_status', 'sim_message'])
            writer.writerow([sc_idx, status, str(message).replace('\n', ' ')[:500]])
    except Exception:
        pass

def reset_events_and_outserv(pf):
    pf.ResetCalculation()

    event_connector = pf.GetCalcRelevantObjects("EventConnector.ElmCoup")[0]
    event_connector.SetAttribute("bus1", None)
    event_connector.SetAttribute("bus2", None)

    tmp_cubics = pf.GetCalcRelevantObjects('*evemt_tmp_cubic.StaCubic')
    for tmp_cubic in tmp_cubics:
        tmp_cubic.Delete()

    active_study_case = pf.GetActiveStudyCase()
    inc = active_study_case.GetContents('*.ComInc')[0]
    events = inc.p_event

    for event in events.GetContents():
        event.Delete()

def setup_simscan(pf):
    active_study_case = pf.GetActiveStudyCase()
    inc = active_study_case.GetContents('*.ComInc')[0]
    simscan = active_study_case.GetContents('*WarnScan.ScnVar', 1)[0]
    simscan.simscanobj = inc.p_resvar
    inc.p_simscn = active_study_case.GetContents('*.IntScn')[0]


def calc_ice(pf):
    """
    Calculates the impedance of Ce
    """
    lines = pf.GetCalcRelevantObjects('*.ElmLne')
    sum_ice = 0
    for line in lines:
        if ((line.GetAttribute("loc_name") not in ["LnOHLSwitch", "LnCableSwitch"]) and not line.GetAttribute("outserv")):
            sum_ice += line.GetAttribute("Ice")
    return sum_ice

def calc_pet_reactance(ice, i_r, vn):
    """
    Calculates the reactance of the Petersen Coil
    """
    i_pet = i_r + ice
    i_pet = max(0.1, i_pet)  # do not allow negative values for edge cases
    x_pet = math.sqrt(3) * vn / (3 * i_pet)

    return x_pet

def get_event_source_bus(pf, selected_event):
    if selected_event == "switch_inrushLV":
        event_source_bus = pf.GetCalcRelevantObjects("BusInrushLVA.ElmTerm")[0]
    elif selected_event == "switch_inrushHV":
        event_source_bus = pf.GetCalcRelevantObjects("BusInrushHVA.ElmTerm")[0]
    elif selected_event == "switch_load_on":
        event_source_bus = pf.GetCalcRelevantObjects("BusLoadSwitchA.ElmTerm")[0]
    elif selected_event == "switch_load_off":
        event_source_bus = pf.GetCalcRelevantObjects("BusLoadSwitchA.ElmTerm")[0]
    elif selected_event == "switch_cap_on":
        event_source_bus = pf.GetCalcRelevantObjects("BusCapSwitch.ElmTerm")[0]
    elif selected_event == "switch_cap_off":
        event_source_bus = pf.GetCalcRelevantObjects("BusCapSwitch.ElmTerm")[0]
    elif selected_event == "switch_ohl_on":
        event_source_bus = pf.GetCalcRelevantObjects("BusOHLSwitchA.ElmTerm")[0]
    elif selected_event == "switch_ohl_off":
        event_source_bus = pf.GetCalcRelevantObjects("BusOHLSwitchA.ElmTerm")[0]
    elif selected_event == "switch_cable_on":
        event_source_bus = pf.GetCalcRelevantObjects("BusCableSwitchA.ElmTerm")[0]
    elif selected_event == "switch_cable_off":
        event_source_bus = pf.GetCalcRelevantObjects("BusCableSwitchA.ElmTerm")[0]
    elif selected_event == "switch_motor_start":
        event_source_bus = pf.GetCalcRelevantObjects("BusMotorStartA.ElmTerm")[0]
    else:
        raise ValueError("Unsupported event type")

    return event_source_bus

def get_switch_info(pf, selected_event):
    if selected_event == "switch_inrushLV":
        target_switch = pf.GetCalcRelevantObjects("SwitchInrushLV.StaSwitch")[0]
        initial_state = 0
        final_state = 1
    elif selected_event == "switch_inrushHV":
        target_switch = pf.GetCalcRelevantObjects("SwitchInrushHV.StaSwitch")[0]
        initial_state = 0
        final_state = 1
    elif selected_event == "switch_load_on":
        target_switch = pf.GetCalcRelevantObjects("SwitchLoadSwitch.StaSwitch")[0]
        initial_state = 0
        final_state = 1
    elif selected_event == "switch_load_off":
        target_switch = pf.GetCalcRelevantObjects("SwitchLoadSwitch.StaSwitch")[0]
        initial_state = 1
        final_state = 0
    elif selected_event == "switch_cap_on":
        target_switch = pf.GetCalcRelevantObjects("SwitchCapacitance.StaSwitch")[0]
        initial_state = 0
        final_state = 1
    elif selected_event == "switch_cap_off":
        target_switch = pf.GetCalcRelevantObjects("SwitchCapacitance.StaSwitch")[0]
        initial_state = 1
        final_state = 0
    elif selected_event == "switch_ohl_on":
        target_switch = pf.GetCalcRelevantObjects("SwitchOHL.StaSwitch")[0]
        initial_state = 0
        final_state = 1
    elif selected_event == "switch_ohl_off":
        target_switch = pf.GetCalcRelevantObjects("SwitchOHL.StaSwitch")[0]
        initial_state = 1
        final_state = 0
    elif selected_event == "switch_cable_on":
        target_switch = pf.GetCalcRelevantObjects("SwitchCable.StaSwitch")[0]
        initial_state = 0
        final_state = 1
    elif selected_event == "switch_cable_off":
        target_switch = pf.GetCalcRelevantObjects("SwitchCable.StaSwitch")[0]
        initial_state = 1
        final_state = 0
    elif selected_event == "switch_motor_start":
        target_switch = pf.GetCalcRelevantObjects("SwitchMotorStart.StaSwitch")[0]
        initial_state = 0
        final_state = 1
    else:
        raise ValueError("Unsupported event type")

    return target_switch, initial_state, final_state

def get_shc_type(selected_event):
    # 0: 3 - phasiger Kurzschluss
    # 1: 2 - phasiger Kurzschluss
    # 2: 1 - phasiger Erdschluss
    # 3: 2 - phasiger Erdschluss

    if (selected_event == "flt_1phg_shc" or
            selected_event == "flt_1phg_shc_w_arc" or
            selected_event == "flt_1phg_hif" or
            selected_event == "flt_1phg_hif_w_arc" or
            selected_event == "flt_1phg_incipient" or
            selected_event == "flt_1phg_incipient_w_arc"):
        return 2
    elif selected_event == "flt_2ph_shc":
        return 1
    elif selected_event == "flt_2phg_shc":
        return 3
    elif selected_event == "flt_3ph_shc":
        return 0
    else:
        raise ValueError("Unsupported event type")

def get_phase_int(settings):
    if settings["events"]["event_type"] in ["flt_2ph_shc", "flt_2phg_shc"]:
        if settings["events"]["event_phase_select_2ph"] == 'ab':
            phase_int = 0
        elif settings["events"]["event_phase_select_2ph"] == 'bc':
            phase_int = 1
        elif settings["events"]["event_phase_select_2ph"] == 'ca':
            phase_int = 2
        else:
            raise ValueError("Invalid phase selection for 2-phase event")
    elif settings["events"]["event_type"] in ["flt_1phg_shc", "flt_1phg_hif", "flt_1phg_incipient", "flt_1phg_shc_w_arc", "flt_1phg_hif_w_arc", "flt_1phg_incipient_w_arc"]:
        if settings["events"]["event_phase_select_1ph"] == 'a':
            phase_int = 0
        elif settings["events"]["event_phase_select_1ph"] == 'b':
            phase_int = 1
        elif settings["events"]["event_phase_select_1ph"] == 'c':
            phase_int = 2
        else:
            raise ValueError("Invalid phase selection for 1-phase event")
    elif settings["events"]["event_type"] == "flt_3ph_shc":
        phase_int = 0
    else:
        raise ValueError("Unsupported event type")
    return phase_int


# ========================================== CREATE EVENTS ========================================== #
def create_switch_event(pf, settings):
    selected_event = settings["events"]["event_type"]
    active_study_case = pf.GetActiveStudyCase()
    inc = active_study_case.GetContents('*.ComInc')[0]
    events = inc.p_event

    # connect the event switch and create the switching event.
    event_connector = pf.GetCalcRelevantObjects("EventConnector.ElmCoup")[0]
    event_source_bus = get_event_source_bus(pf, selected_event)
    event_switch_target_bus = pf.GetCalcRelevantObjects(f"{settings['events']['event_target']}.ElmTerm")[0]
    source_cubic = event_source_bus.CreateObject('StaCubic', 'evemt_tmp_cubic')
    target_cubic = event_switch_target_bus.CreateObject('StaCubic', 'evemt_tmp_cubic')
    event_connector.SetAttribute("bus1", source_cubic)
    event_connector.SetAttribute("bus2", target_cubic)

    target_switch, initial_state, final_state = get_switch_info(pf, selected_event)

    target_switch.SetAttribute('on_off', initial_state)

    event = events.CreateObject('EvtSwitch')
    event.loc_name = "switch_event"
    event.time = settings['events']['event_start']
    event.p_target = target_switch
    event.i_switch = final_state

def create_trip_event(pf, settings):
    selected_event = settings["events"]["event_type"]
    active_study_case = pf.GetActiveStudyCase()

    inc = active_study_case.GetContents('*.ComInc')[0]
    events = inc.p_event

    event_switch_target_bus = pf.GetCalcRelevantObjects(f"{settings['events']['event_target']}.ElmTerm")[0]

    min_distance = float('inf')
    closes_target = None

    if selected_event == 'switch_ibr_trip':
        possible_targets = pf.GetCalcRelevantObjects('*IBR*.ElmVac')
    elif selected_event == 'switch_gen_trip':
        possible_targets = pf.GetCalcRelevantObjects('*.ElmSym')
    else:
        raise NotImplementedError

    for possible_target in possible_targets:
        distance = event_switch_target_bus.GetMinDistance(possible_target.bus1.cterm)
        if distance < min_distance:
            closes_target = possible_target
            min_distance = distance

    event = events.CreateObject('EvtSwitch')
    event.loc_name = "switch_event"
    event.time = settings['events']['event_start']
    event.p_target = closes_target
    event.i_switch = 0


def create_fault_event(pf, settings, arc_on):
    selected_event = settings["events"]["event_type"]
    active_study_case = pf.GetActiveStudyCase()
    inc = active_study_case.GetContents('*.ComInc')[0]
    events = inc.p_event

    fault_target = pf.GetCalcRelevantObjects(f"*{settings['events']['event_target']}.ElmTerm, *{settings['events']['event_target']}.ElmLne")[0]

    pf.PrintPlain(fault_target)

    if fault_target.GetClassName() == 'ElmLne':
        global CLEANUP_DICT
        # store information for later cleanup
        CLEANUP_DICT["required"] = True
        CLEANUP_DICT["line_orig_length"] = fault_target.dline
        CLEANUP_DICT["line_bus1"] = fault_target.bus1
        CLEANUP_DICT["line_bus2"] = fault_target.bus2

        fault_loc = settings['events']['event_flt_target_line_location']
        fault_term = pf.SplitLine(fault_target, fault_loc)
        assert fault_term is not None, f"Failed to split line {fault_target.loc_name}"

        # recalculate the line after splitting it
        fault_line1 = pf.GetCalcRelevantObjects(f"{fault_target.loc_name}.ElmLne")[0]
        fault_line2 = pf.GetCalcRelevantObjects(f"{fault_target.loc_name}(1).ElmLne")[0]
        fault_line1.FitParams()
        fault_line2.FitParams()

        CLEANUP_DICT["line_main"] = fault_line1
        CLEANUP_DICT["line_split"] = fault_line2
        CLEANUP_DICT["fault_term"] = fault_term

    elif fault_target.GetClassName() == 'ElmTerm':
        fault_term = fault_target
    else:
        raise NotImplementedError("Fault target not supported")

    if arc_on:
        arc_model_bus = pf.GetCalcRelevantObjects("BusArcModelA.ElmTerm")[0]
        event = events.CreateObject('EvtShcll')
        event.loc_name = "shc_event"
        event.time = settings['events']['event_start']
        event.i_shc = int(1)  # setting one phase intercircuit fault means we have to set 1 here.

        event.p_target = fault_term
        event.iPhase1 = get_phase_int(settings)

        event.p_target2 = arc_model_bus
        event.iPhase2 = int(0)
    else:
        event = events.CreateObject('EvtShc')
        event.loc_name = "shc_event"
        event.time = settings['events']['event_start']
        event.p_target = fault_term
        event.i_shc = get_shc_type(selected_event)
        phase_int = get_phase_int(settings)
        event.i_p2psc = phase_int
        event.i_p2pgf = phase_int
        event.i_pspgf = phase_int

    if 'hif' in selected_event:
        event.R_f = settings['events']['event_flt_hif_resistance']
    else:
        event.R_f = settings['events']['event_flt_shc_resistance']

def create_ifault(pf, settings, arc_on):
    selected_event = settings["events"]["event_type"]
    active_study_case = pf.GetActiveStudyCase()
    inc = active_study_case.GetContents('*.ComInc')[0]
    events = inc.p_event

    fault_target = pf.GetCalcRelevantObjects(f"*{settings['events']['event_target']}.ElmTerm, *{settings['events']['event_target']}.ElmLne")[0]

    pf.PrintPlain(fault_target)

    if fault_target.GetClassName() == 'ElmLne':
        global CLEANUP_DICT
        # store information for later cleanup
        CLEANUP_DICT["required"] = True
        CLEANUP_DICT["line_orig_length"] = fault_target.dline
        CLEANUP_DICT["line_bus1"] = fault_target.bus1
        CLEANUP_DICT["line_bus2"] = fault_target.bus2

        fault_loc = settings['events']['event_flt_target_line_location']
        fault_term = pf.SplitLine(fault_target, fault_loc)
        assert fault_term is not None, f"Failed to split line {fault_target.loc_name}"

        # recalculate the line after splitting it
        fault_line1 = pf.GetCalcRelevantObjects(f"{fault_target.loc_name}.ElmLne")[0]
        fault_line2 = pf.GetCalcRelevantObjects(f"{fault_target.loc_name}(1).ElmLne")[0]
        fault_line1.FitParams()
        fault_line2.FitParams()

        CLEANUP_DICT["line_main"] = fault_line1
        CLEANUP_DICT["line_split"] = fault_line2
        CLEANUP_DICT["fault_term"] = fault_term

    elif fault_target.GetClassName() == 'ElmTerm':
        fault_term = fault_target
    else:
        raise NotImplementedError("Fault target not supported")

    # Create fault with or without arc model
    if arc_on:
        arc_model_bus = pf.GetCalcRelevantObjects("BusArcModelA.ElmTerm")[0]
        event = events.CreateObject('EvtShcll')
        event.loc_name = "incipient_event"
        event.time = settings['events']['event_start']
        event.i_shc = int(1)  # setting one phase intercircuit fault means we have to set 1 here.

        event.p_target = fault_term
        event.iPhase1 = get_phase_int(settings)

        event.p_target2 = arc_model_bus
        event.iPhase2 = int(0)

        # incipient faults shall always have hif resistance
        event.R_f = settings['events']['event_flt_hif_resistance']

        # create clearing event
        event_clearing = events.CreateObject('EvtShcll')
        event_clearing.loc_name = 'ClearingEvent'
        event_clearing.time = settings['events']['event_start'] + settings['events']['event_iflt_duration']
        event_clearing.i_shc = int(0)  # clearing intercircuit fault means we have to set 0 here.
        event_clearing.p_target = fault_term
        event_clearing.p_target2 = arc_model_bus
        event_clearing.i_clearShc = int(1)

    else:
        event = events.CreateObject('EvtShc')
        event.loc_name = "incipient shc_event"
        event.time = settings['events']['event_start']
        event.p_target = fault_term
        event.i_shc = get_shc_type(selected_event)
        event.i_pspgf = get_phase_int(settings)

        # incipient faults shall always have hif resistance
        event.R_f = settings['events']['event_flt_hif_resistance']

        # create clearing event with random time
        ground_fault_clearing = events.CreateObject('EvtShc')
        ground_fault_clearing.loc_name = 'ClearingEvent'
        ground_fault_clearing.time = settings['events']['event_start'] + settings['events']['event_iflt_duration']
        ground_fault_clearing.i_shc = int(4)  # clearing shc fault means we have to set 4 here.
        ground_fault_clearing.p_target = fault_term
        ground_fault_clearing.i_clearShc = int(1)



# ========================================== APPLY SETTINGS ========================================== #

def apply_export_settings(pf, settings):
    active_study_case = pf.GetActiveStudyCase()
    exp = active_study_case.GetContents('ExportEvemt.ComRes')[0]
    exp.SetAttribute('f_name', settings['general']['result_file_path'])


def apply_load_settings(pf, settings):
    parent_lib = pf.GetActiveProject().GetContents('*Main*.ElmNet', 1)[0].GetContents(f"*CustomTypeLib*")[0]
    load_lib = parent_lib.GetContents("*LoadTypes*")[0]

    if "loads" in settings.keys():
        for load_name, attrs in settings["loads"].items():
            if not math.isnan(attrs['load_p']):
                load = pf.GetCalcRelevantObjects(f"{load_name}.ElmLod")[0]

                # check if load type exists in attrs
                if 'load_type' in attrs:
                    load_type = load_lib.GetContents(f"*{attrs['load_type']}*")[0]
                    load.typ_id = load_type

                load.mode_inp = 'PQ'
                load.SetAttribute("plini", attrs["load_p"])
                load.SetAttribute("qlini", attrs["load_q"])


def apply_gen_settings(pf, settings):
    if settings["general"]["vn"] >= 110:
        if "gens" in settings.keys():
            for gen_name, attrs in settings["gens"].items():
                if not math.isnan(attrs['pgen']):
                    generator = pf.GetCalcRelevantObjects(f"{gen_name}.ElmSym")[0]
                    generator.pgini = attrs["pgen"]
                    generator.usetp = attrs["usetp"]


def apply_grounding_settings(pf, settings):
    if "grounding" in settings.keys():
        active_project = pf.GetActiveProject()
        main_grid = active_project.GetContents('*Main*.ElmNet', 1)[0]
        trafos = main_grid.GetContents("*.ElmTr2")

        # Apply grounding settings
        try:
            grnd_res = pf.GetCalcRelevantObjects("StarpointPermRes.ElmVac")[0]
            petersen_coil = pf.GetCalcRelevantObjects("PetersenCoil.ElmVac")[0]
        except IndexError:
            return

        if settings["grounding"]["grnd_type"] == "solid":
            grnd_res.SetAttribute("R1", settings["grounding"]["solid_ground_resistance"])
            petersen_coil.SetAttribute("outserv", True)

            for trafo in trafos:
                # ground all trafos to have solid grounding
                trafo.cgnd_h = 0
                trafo.cgnd_l = 0

        elif settings["grounding"]["grnd_type"] == "resistive":
            grnd_res.SetAttribute("R1", settings["grounding"]["resistive_ground_resistance"])
            petersen_coil.SetAttribute("outserv", True)

            for trafo in trafos:
                # do not ground all trafos to have one place for resistive grounding
                trafo.cgnd_h = 1
                trafo.cgnd_l = 1

        elif settings["grounding"]["grnd_type"] == "resonant":
            petersen_coil.SetAttribute("outserv", False)

            i_ce = calc_ice(pf)
            x_pet = calc_pet_reactance(i_ce, settings["grounding"]["coil_tuning"], settings["general"]["vn"]*1000)

            petersen_coil.SetAttribute("X1", x_pet)
            grnd_res.SetAttribute("R1", x_pet / (settings["grounding"]["parasitic_resistance_percentage"] / 100))

            for trafo in trafos:
                # do not ground all trafos to have one place for resonant grounding
                trafo.cgnd_h = 1
                trafo.cgnd_l = 1

        else:
            raise ValueError("Invalid grounding type specified")


def apply_ext_grid_settings(pf, settings):
    if "ExtGrid" in settings.keys():
        ext_grids = pf.GetActiveProject().GetContents('*Main*.ElmNet', 1)[0].GetContents('*.ElmXnet*')
        for ext_grid in ext_grids:
            ext_grid.bustp = 'SL'
            ext_grid.SetAttribute("usetp", settings["ExtGrid"]["usetp"])
            ext_grid.SetAttribute("phiini", settings["ExtGrid"]["phiini"])


def apply_ohl_switch_settings(pf, settings):
    if "ohl_switch" in settings.keys():
        parent_lib = pf.GetActiveProject().GetContents('*Main*.ElmNet', 1)[0].GetContents(f"*CustomTypeLib*")[0]

        line_lib = parent_lib.GetContents("*OHLTypes*")[0].GetContents(f"*{settings['general']['fn']}*")[0].GetContents(f"*{settings['general']['vn']}kV*")[0]
        tower_name = settings["ohl_switch"]["ohl_type"]
        tower_type = line_lib.GetContents(f"*{tower_name}.TypTow")[0]

        ohl_switch_line = pf.GetCalcRelevantObjects(f"LnOHLSwitch.ElmLne")[0]
        ohl_switch_line.typ_id = tower_type
        ohl_switch_line.dline = settings["ohl_switch"]["ohl_length"]

        ohl_switch_line.i_dist = 1
        ohl_switch_line.i_model = 2
        ohl_switch_line.fd_model = 0
        ohl_switch_line.ftau = settings["general"]["fn"]
        ohl_switch_line.fmin = 0.01
        ohl_switch_line.fmax = 1000000
        ohl_switch_line.FitParams()


def apply_cable_switch_settings(pf, settings):
    if "cable_switch" in settings.keys():
        if settings["general"]["vn"] == 20:
            parent_lib = pf.GetActiveProject().GetContents('*Main*.ElmNet', 1)[0].GetContents(f"*CustomTypeLib*")[0]

            cable_lib = parent_lib.GetContents("*Cables*")[0].GetContents(f"*20kV*")[0]
            cable_name = settings["cable_switch"]["cable_type"]
            cable_type = cable_lib.GetContents(f"*{cable_name}.TypCabsys")[0]

            cable_switch_line = pf.GetCalcRelevantObjects(f"LnCableSwitch.ElmLne")[0]
            cable_switch_line.typ_id = cable_type
            cable_switch_line.dline = settings["cable_switch"]["cable_length"]

            cable_switch_line.i_dist = 1
            cable_switch_line.i_model = 2
            cable_switch_line.fd_model = 0
            cable_switch_line.ftau = settings["general"]["fn"]
            cable_switch_line.fmin = 0.01
            cable_switch_line.fmax = 1000000
            cable_switch_line.FitParams()


def apply_transformer_switch_settings(pf, settings):
    fn = settings["general"]["fn"]
    vn = settings["general"]["vn"]
    parent_lib = pf.GetActiveProject().GetContents('*Main*.ElmNet', 1)[0].GetContents(f"*CustomTypeLib*")[0]

    if "switch_trafo_to_lv_type" in settings.keys():
        if vn == 110:
            trafo_to_lv_lib = \
                parent_lib.GetContents("*TrafoTypes*")[0].GetContents(f"*{fn}*")[0].GetContents(f"*GridTrafos*")[0].GetContents(
                    f"*{vn}/20*")[0]
        else:
            trafo_to_lv_lib = \
                parent_lib.GetContents("*TrafoTypes*")[0].GetContents(f"*{fn}*")[0].GetContents(f"*GridTrafos*")[0].GetContents(
                    f"*{vn}/*")[0]

        trf_inrush_lv = pf.GetCalcRelevantObjects(f"TrfInrushLV.ElmTr2")[0]
        trf_inrush_lv.typ_id = trafo_to_lv_lib.GetContents(f"*{settings['switch_trafo_to_lv_type']}.TypTr2")[0]

    if "switch_trafo_to_hv_type" in settings.keys():
        if not vn == 345:
            trafo_to_hv_lib = \
            parent_lib.GetContents("*TrafoTypes*")[0].GetContents(f"*{fn}*")[0].GetContents(f"*GridTrafos*")[0].GetContents(
                f"*/{vn}*")[0]
            trf_inrush_hv = pf.GetCalcRelevantObjects(f"TrfInrushHV.ElmTr2")[0]
            trf_inrush_hv.typ_id = trafo_to_hv_lib.GetContents(f"*{settings['switch_trafo_to_hv_type']}.TypTr2")[0]


def apply_cap_switch_settings(pf, settings):
    # Apply capacitance settings
    if "cap_switch" in settings.keys():
        capacitance = pf.GetCalcRelevantObjects("CapSwitch.ElmShnt")[0]
        capacitance.SetAttribute("qcapn", settings["cap_switch"]["cap_power"])


def apply_motor_switch_settings(pf, settings):
    if "motor_start" in settings.keys():
        fn = settings["general"]["fn"]
        vn = settings["general"]["vn"]
        parent_lib = pf.GetActiveProject().GetContents('*Main*.ElmNet', 1)[0].GetContents(f"*CustomTypeLib*")[0]

        if vn == 110:
            motor_lib = parent_lib.GetContents("*AsymTypes*")[0].GetContents(f"*11kV*")[0]
            motor_trafo_lib = \
            parent_lib.GetContents("*TrafoTypes*")[0].GetContents(f"*{fn}*")[0].GetContents(f"*GridTrafos*")[0].GetContents(
                f"*110/11kV*")[0]
        elif vn == 20:
            motor_lib = parent_lib.GetContents("*AsymTypes*")[0].GetContents(f"*0_4kV*")[0]
            motor_trafo_lib = \
            parent_lib.GetContents("*TrafoTypes*")[0].GetContents(f"*{fn}*")[0].GetContents(f"*GridTrafos*")[0].GetContents(
                f"*20/0_4kV*")[0]
        else:
            return

        motor_start = pf.GetCalcRelevantObjects("*MotorStart.ElmAsm")[0]
        trafo_motor = pf.GetCalcRelevantObjects("*TrfMotorStart.ElmTr2")[0]

        motor_start.typ_id = motor_lib.GetContents(f"*{settings['motor_start']['motor_type']}.TypAsmo")[0]
        trafo_motor.typ_id = motor_trafo_lib.GetContents(f"*{settings['motor_start']['motor_trafo_type']}.TypTr2")[0]


def apply_arc_settings(pf, settings):
    if "arc" in settings.keys() and "w_arc" in settings["events"]["event_type"]:
        arc_dsl_model = pf.GetCalcRelevantObjects("*ArcDsl.ElmDsl")[0]
        arc_dsl_model.SetAttribute("tau", float(settings["arc"]["arc_tau"]))
        arc_dsl_model.SetAttribute("u0", float(settings["arc"]["arc_u0"]))
        arc_dsl_model.SetAttribute("r0", float(settings["arc"]["arc_r0"]))

def apply_event_settings(pf, settings):
    pf.PrintPlain('Selected Event')
    selected_event = settings["events"]["event_type"]
    if "_w_arc" in selected_event:
        arc_on = True
    else:
        arc_on = False
    if "switch_" in selected_event:
        if "trip" in selected_event:
            create_trip_event(pf, settings)
        else:
            create_switch_event(pf, settings)
    elif "flt_" in selected_event and not "_incipient" in selected_event:
        create_fault_event(pf, settings, arc_on)
    elif "flt_" in selected_event and "_incipient" in selected_event:
        create_ifault(pf, settings, arc_on)
    elif "NoEvent" in selected_event:
        pass
    else:
        raise ValueError(f"Event type {selected_event} not recognized.")


# ========================================== EXECUTE SIMULATION ========================================== #

def simulate_and_export(pf):
    """
    Runs initialization and simulation and exports the results only if both succeed.
    Returns a (status, message) tuple, status in {success, init_failed, sim_failed, convergence_warning}.
    """
    sc = pf.GetActiveStudyCase()
    inc = sc.GetContents('*.ComInc')[0]
    inc_result = inc.Execute()

    if inc_result == 0 or inc_result == 1:
        sim = sc.GetContents('*.ComSim')[0]
        sim_result = sim.Execute()
        n_warnings = sim.GetTotalWarnA()

        if sim_result == 0 and n_warnings == 0:
            exp = sc.GetContents('ExportEvemt.ComRes')[0]
            exp_result = exp.Execute()
            return 'success', f'ComRes returned {exp_result}'
        else:
            file_folder = os.path.dirname(os.path.abspath(__file__))
            if sim_result >0:
                with open(f'{file_folder}\error_log.txt', 'a') as f:
                    f.write('Simulation failed.' + '\n')
                return 'sim_failed', f'ComSim returned {sim_result}'
            elif n_warnings > 0:
                with open(f'{file_folder}\error_log.txt', 'a') as f:
                    f.write('Simulation convergence failed.' + '\n')
                return 'convergence_warning', f'{n_warnings} simulation warnings (ComSim returned {sim_result})'
            return 'sim_failed', f'ComSim returned {sim_result}'
    else:
        file_folder = os.path.dirname(os.path.abspath(__file__))
        with open(f'{file_folder}\error_log.txt', 'a') as f:
            f.write('Initialization failed.' + '\n')
        return 'init_failed', f'ComInc returned {inc_result}'


def cleanup():
    global CLEANUP_DICT
    if CLEANUP_DICT["required"]:
        # Remove fault
        CLEANUP_DICT["line_split"].Delete()
        CLEANUP_DICT["fault_term"].Delete()
        CLEANUP_DICT["line_main"].bus1 = CLEANUP_DICT["line_bus1"]
        CLEANUP_DICT["line_main"].bus2 = CLEANUP_DICT["line_bus2"]
        CLEANUP_DICT["line_main"].dline = CLEANUP_DICT["line_orig_length"]
        CLEANUP_DICT["line_main"].FitParams()
    else:
        return

# Function to apply settings from the dictionary
def main():
    pf = powerfactory.GetApplication()
    pf.ClearOutputWindow()
    script = pf.GetCurrentScript()
    sc_idx = script.sc_idx
    setting_file_path = script.setting_file_path

    settings = csv_to_nested_dicts(setting_file_path, sc_idx)

    pf.PrintPlain(settings)

    reset_events_and_outserv(pf)
    setup_simscan(pf)
    apply_export_settings(pf, settings)

    apply_load_settings(pf, settings)
    apply_gen_settings(pf, settings)
    apply_grounding_settings(pf, settings)
    apply_ext_grid_settings(pf, settings)

    apply_ohl_switch_settings(pf, settings)
    apply_cable_switch_settings(pf, settings)
    apply_transformer_switch_settings(pf, settings)
    apply_cap_switch_settings(pf, settings)
    apply_motor_switch_settings(pf, settings)

    apply_arc_settings(pf, settings)
    apply_event_settings(pf, settings)

    pf.PrintPlain('Settings Applied')

    status, message = simulate_and_export(pf)

    cleanup()

    write_sim_status(setting_file_path, sc_idx, status, message)

try:
    main()
    file_folder = os.path.dirname(os.path.abspath(__file__))
    with open(f'{file_folder}\error_log.txt', 'a') as f:
        f.write('Success' + '\n')

except Exception as e:
     # write to a log file
     file_folder = os.path.dirname(os.path.abspath(__file__))
     with open(f'{file_folder}\error_log.txt', 'a') as f:
        f.write(traceback.format_exc() + '\n')
        try:
            pf = powerfactory.GetApplication()
            script = pf.GetCurrentScript()
            setting_file_path = script.setting_file_path
            sc_idx = script.sc_idx
            write_sim_status(setting_file_path, sc_idx, 'exception', traceback.format_exc().strip().splitlines()[-1])
            settings = csv_to_nested_dicts(setting_file_path, sc_idx)
            f.write(f"Previous Error Occured for file path {settings['general']['result_file_path']}, Studycase ID {sc_idx}, Setting File Path {setting_file_path}" + '\n')
        except:
            # if this fails, we cant get information.
            pass

     raise e