import os
import pickle
import sys
import math

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# a bit of a workaround for files executed from powerfactory directly...
file_location = __file__
parent_directory = os.path.dirname(os.path.abspath(file_location))
main_directory = os.path.dirname(os.path.abspath(parent_directory))
sys.path.append(parent_directory)
sys.path.append(main_directory)

import numpy as np

from parameter_sampling.param_rand_sampling import *
from util.dc_check import growing_dc
from util.pf_prepare_models import prepare_model

MIN_AC_AMPLITUDE_A = 0.1  # currents with a smaller AC amplitude (in practice neutral-point currents close to zero) are
#                           excluded from the cycle-to-cycle steady-state check


def create_slack(bus, node, vn, main_grid, ext_grid_sampler, grounding_sampler):
    slack_grid = main_grid.CreateObject('ElmXnet', 'Slack')
    slack_grid.bustp = 'SL'
    slack_grid.usetp = ext_grid_sampler.get_usetp()
    slack_grid.phiini = ext_grid_sampler.get_phiini()
    slack_grid.snss = ext_grid_sampler.get_sn()
    slack_grid.rntxn = ext_grid_sampler.get_rntxn()
    slack_grid.x0tx1 = ext_grid_sampler.get_x0tx1()
    slack_grid.r0tx0 = ext_grid_sampler.get_r0tx0()

    if vn == 345:
        cubic = bus.CreateObject('StaCubic', 'Cubicle')
        slack_grid.bus1 = cubic
    else:
        bus_slack_grid = main_grid.CreateObject('ElmTerm', 'Bus' + str(node) + 'ExtGrid')
        bus_slack_grid.uknom = 380 if vn == 110 else 110
        cubic_lv = bus.CreateObject('StaCubic', 'Cubicle')
        cubic_hv_trafo = bus_slack_grid.CreateObject('StaCubic', 'Cubicle')
        cubic_hv_extgrid = bus_slack_grid.CreateObject('StaCubic', 'Cubicle')
        slack_trafo = main_grid.CreateObject('ElmTr2', f'Trf{node}-{node}ExtGrid')

        slack_trafo.typ_id = ext_grid_sampler.get_ext_grid_trafo_type()
        slack_trafo.bushv = cubic_hv_trafo
        slack_trafo.buslv = cubic_lv
        slack_trafo.cgnd_h = 0  # For YNyn both must be 0
        slack_trafo.cgnd_l = 0  # For YNyn both must be 0
        slack_trafo.re0tr_l = grounding_sampler.get_solid_resistance()

        slack_grid.bus1 = cubic_hv_extgrid

        bus_np = main_grid.CreateObject('ElmTerm', 'Bus' + str(node) + 'NP')
        bus_np.phtech = 8
        bus_np.uknom = vn
        cubic_np = bus_np.CreateObject('StaCubic', 'Cubicle')
        cubic_main = bus.CreateObject('StaCubic', 'Cubicle')
        neutral_point = main_grid.CreateObject('ElmNec', 'NeutralPoint')
        neutral_point.Unom = vn
        neutral_point.Curn = 1
        neutral_point.iintgnd = 2
        neutral_point.bus1 = cubic_main
        neutral_point.bus1n = cubic_np

        np_r = main_grid.CreateObject('ElmVac', 'StarpointPermRes')
        np_r.Unom = vn
        np_r.nphase = 1
        np_r.usetp = 0
        cubic_r = bus_np.CreateObject('StaCubic', 'Cubicle')
        np_r.bus1 = cubic_r

        np_x = main_grid.CreateObject('ElmVac', 'PetersenCoil')
        np_x.Unom = vn
        np_x.nphase = 1
        np_x.usetp = 0
        cubic_x = bus_np.CreateObject('StaCubic', 'Cubicle')
        np_x.bus1 = cubic_x

def create_load(bus, node, main_grid, load_sampler, grounding_sampler):
    load = main_grid.CreateObject('ElmLod', 'Ld' + str(node) + 'LV')
    load_bus = main_grid.CreateObject('ElmTerm', 'Bus' + str(node) + 'Ld')
    load_trafo = main_grid.CreateObject('ElmTr2', f'Trf{node}-{node}Ld')
    load.typ_id = load_sampler.get_load_type()

    p, q = load_sampler.get_pq()
    load.plini = p
    load.qlini = q

    new_cubic_trafo_high = bus.CreateObject('StaCubic', 'Cubicle')
    new_cubic_trafo_low = load_bus.CreateObject('StaCubic', 'Cubicle')
    new_cubic_load = load_bus.CreateObject('StaCubic', 'Cubicle')
    load_switch = new_cubic_load.CreateObject("StaSwitch", "Switch")
    load_switch.Close()

    load.bus1 = new_cubic_load

    load_trafo.typ_id = load_sampler.get_load_trafo_type(p, q)
    load_trafo.bushv = new_cubic_trafo_high
    load_trafo.buslv = new_cubic_trafo_low
    if bus.uknom == 20:
        # do not ground in 20 kV grids
        load_trafo.cgnd_h = 1
    else:
        # connect the others
        load_trafo.cgnd_h = 0

    load_trafo.re0tr_h = grounding_sampler.get_solid_resistance()
    load_trafo.cgnd_l = 0
    load_trafo.re0tr_l = grounding_sampler.get_solid_resistance()

    load_bus.uknom = load_trafo.typ_id.utrn_l


def create_exciter(gen, pf, vn, fn):
    comp_name = gen.loc_name + "_cntrl"
    comp = gen.GetParent().CreateObject("ElmComp", comp_name)
    comp.typ_id = pf.GetCurrentUser().GetContents(f"*CustomTypeLib*")[0].GetContents("Exciter")[0].GetContents("SYM Frame_no droop.BlkDef")[0]
    comp.pmod = 1

    ac1a = pf.GetCurrentUser().GetContents(f"*CustomTypeLib*")[0].GetContents("Exciter")[0].GetContents("avr_ESAC1A.BlkDef")[0]
    udm = pf.GetProjectFolder("blk")
    lib_name = "Cntrl_SynMac"
    if not udm.GetContents(lib_name):
        local_lib = udm.CreateObject("IntFolder", lib_name)
    else:
        local_lib = udm.GetContents(lib_name)[0]

    if not local_lib.GetContents(ac1a.loc_name):
        local_lib.AddCopy(ac1a)

    avr_sampler = ExciterSampler(pf, vn, fn)
    avr_dsl = comp.CreateObject("ElmDsl", comp_name + "_avr_AC1A")
    avr_dsl.typ_id = local_lib.GetContents(ac1a.loc_name)[0]
    avr_dsl.Tr = avr_sampler.get_Tr()
    avr_dsl.Tb = avr_sampler.get_Tb()
    avr_dsl.Tc = avr_sampler.get_Tc()
    avr_dsl.Tb1 = avr_sampler.get_Tb()
    avr_dsl.Tc1 = avr_sampler.get_Tc()
    avr_dsl.Ka = avr_sampler.get_Ka()
    avr_dsl.Ta = avr_sampler.get_Ta()
    avr_dsl.Kc = avr_sampler.get_Kc()
    avr_dsl.Kf = avr_sampler.get_Kf()
    avr_dsl.Tf = avr_sampler.get_Tf()
    avr_dsl.Te = avr_sampler.get_Te()
    avr_dsl.Ke = avr_sampler.get_Ke()
    avr_dsl.Kd = avr_sampler.get_Kd()
    avr_dsl.E1 = avr_sampler.get_E1()
    avr_dsl.SE1 = avr_sampler.get_SE1()
    avr_dsl.E2 = avr_sampler.get_E2()
    avr_dsl.SE2 = avr_sampler.get_SE2()
    avr_dsl.Vamin = avr_sampler.get_Vamin()
    avr_dsl.Vrmin = avr_sampler.get_Vrmin()
    avr_dsl.Vamax = avr_sampler.get_Vamax()
    avr_dsl.Vrmax = avr_sampler.get_Vrmax()

    pelm_list = comp.pelm
    pelm_list[0] = gen
    pelm_list[1] = avr_dsl
    comp.pelm = pelm_list


def create_generator(pf, bus, node, vn, fn, main_grid, sync_machine_sampler, grounding_sampler):
    gen = main_grid.CreateObject('ElmSym', 'G' + str(node))
    gen_bus = main_grid.CreateObject('ElmTerm', 'Bus' + str(node) + 'Gen')
    gen_trafo = main_grid.CreateObject('ElmTr2', f'Trf{node}-{node}Gen')
    new_cubic_trafo_high = bus.CreateObject('StaCubic', 'Cubicle')
    new_cubic_trafo_low = gen_bus.CreateObject('StaCubic', 'Cubicle')
    new_cubic_generator = gen_bus.CreateObject('StaCubic', 'Cubicle')
    gen_switch = new_cubic_generator.CreateObject("StaSwitch", "Switch")
    gen_switch.Close()
    gen.bus1 = new_cubic_generator
    gen.usetp = sync_machine_sampler.get_usetp()
    gen.typ_id = sync_machine_sampler.get_sym_typ()

    gen_trafo.typ_id = sync_machine_sampler.get_sym_trafo_type(gen)
    gen_trafo.bushv = new_cubic_trafo_high
    gen_trafo.buslv = new_cubic_trafo_low
    gen_trafo.cgnd_h = 0
    gen_trafo.re0tr_h = grounding_sampler.get_solid_resistance()
    gen_trafo.cgnd_l = 0
    gen_trafo.re0tr_l = grounding_sampler.get_solid_resistance()

    gen_bus.uknom = gen.typ_id.ugn
    gen.iqtype = True
    gen.Pmax_uc = gen.typ_id.sgn * gen.typ_id.cosn
    gen.av_mode = "constv"
    create_exciter(gen, pf, vn, fn)



def create_ibr(pf, bus, node, vn, fn, main_grid, sn):
    if vn == 20:
        usc = 6.0  # %
        pcu = 18.0  # kW
    elif vn == 110:
        usc = 12.0  # %
        pcu = 130  # kW
    else:
        raise NotImplementedError

    zbase = vn ** 2 / sn
    zsc = usc / 100
    rsc = pcu / 1000 / sn
    xsc = math.sqrt(zsc ** 2 - rsc ** 2)

    trafo_x = xsc * zbase
    trafo_r = rsc * zbase

    ibr = main_grid.CreateObject('ElmVac', 'IBR' + str(node))

    ibr.Unom = vn
    ibr_bus = main_grid.CreateObject('ElmTerm', 'Bus' + str(node) + 'IBR')

    ibr_trafo = main_grid.CreateObject('ElmSind', f'Ind{node}-{node}IBR')
    new_cubic_trafo_grid = bus.CreateObject('StaCubic', 'Cubicle')
    new_cubic_trafo_ibr = ibr_bus.CreateObject('StaCubic', 'Cubicle')
    new_cubic_ibr = ibr_bus.CreateObject('StaCubic', 'Cubicle')
    ibr_switch = new_cubic_ibr.CreateObject("StaSwitch", "Switch")
    ibr_switch.Close()

    ibr.bus1 = new_cubic_ibr
    ibr.unom = vn

    ibr_trafo.bus1 = new_cubic_trafo_grid
    ibr_trafo.bus2 = new_cubic_trafo_ibr


    ibr_trafo.xrea = trafo_x
    ibr_trafo.rrea = trafo_r
    ibr_trafo.R0toR1 = 1000000000
    ibr_trafo.X0toX1 = 1000000000
    ibr_trafo.ucn = vn
    ibr_trafo.Sn = sn

    ibr_bus.uknom = vn
    comp_name = ibr.loc_name + "_cntrl"
    comp = ibr.GetParent().CreateObject("ElmComp", comp_name)
    comp.typ_id = pf.GetCurrentUser().GetContents(f"*CustomTypeLib*")[0].GetContents("IBRModel")[0].GetContents("IBRModel.BlkDef")[0]

    ibr_voltage_controller = comp.CreateObject("ElmLdfctrl", "VoltageCtrlIBR" + str(node))
    ibr_voltage_controller.i_ctrl = 3  # reactive power
    ibr_voltage_controller.p_cub = new_cubic_trafo_grid
    ibr.p_uctrl = ibr_voltage_controller

    ibr_angle_controller = comp.CreateObject("ElmLdfctrl", "AngleCtrlIBR" + str(node))
    ibr_angle_controller.i_ctrl = 2  # active power
    ibr_angle_controller.p_cub = new_cubic_trafo_grid
    ibr.p_phictrl = ibr_angle_controller

    pelm_list = comp.pelm

    fmu_ibr_ctrl = comp.CreateObject("ElmMdl", comp_name + "FMUIBRController")
    fmu_ibr_ctrl.typ_id = pf.GetCurrentUser().GetContents(f"*CustomTypeLib*")[0].GetContents("IBRModel")[0].GetContents("FMUIBRController.TypMdl")[0]
    fmu_cfg_script = fmu_ibr_ctrl.configScript
    fmu_cfg_script.SetAttribute("obj_id", [bus])

    pelm_list[0] = fmu_ibr_ctrl
    pelm_list[1] = ibr

    ibr_ctrl_ct = comp.CreateObject("StaCt", comp_name + "CT")
    ibr_ctrl_vt = comp.CreateObject("StaVt", comp_name + "VT")
    ibr_ctrl_ct.pbranch = new_cubic_trafo_grid
    ibr_ctrl_vt.pbusbar = bus

    pelm_list[2] = ibr_ctrl_ct
    pelm_list[3] = ibr_ctrl_vt

    negator_currents = comp.CreateObject("ElmDsl", comp_name + "negate_curr")
    volt_to_kv = comp.CreateObject("ElmDsl", comp_name + "v_to_kv")

    negator_currents.typ_id = pf.GetCurrentUser().GetContents(f"*CustomTypeLib*")[0].GetContents("IBRModel")[0].GetContents("NegateCurrents.BlkDef")[0]
    volt_to_kv.typ_id = pf.GetCurrentUser().GetContents(f"*CustomTypeLib*")[0].GetContents("IBRModel")[0].GetContents("VoltToKV.BlkDef")[0]

    pelm_list[4] = negator_currents
    pelm_list[5] = volt_to_kv

    comp.pelm = pelm_list

    fmu_ibr_ctrl.Check()
    pf.SetWriteCacheEnabled(1)
    fmu_ibr_ctrl.SetAttribute("fmuCsSampling", 2)
    fmu_ibr_ctrl.SetAttribute("fmuCSOutputsDelayed", 0)

    # for noticing unset parameters
    ibr.c_pmod.pelm[0].attrvalue = [1000000000000000000000] * len(ibr.c_pmod.pelm[0].attrvalue)

    ibase = (sn * 1e6) / (vn*1e3) / math.sqrt(3) * math.sqrt(2)  # A (peak)
    vbase = (vn*1e3) / math.sqrt(3) * math.sqrt(2)  # V (peak)
    zbase = ((vn*1e3) ** 2) / (sn * 1e6)  # Ohm

    lconv = trafo_x / (2 * math.pi * fn)

    kp_cc = 0.075
    ki_cc = 0.22

    # Control parameters (renamed)
    fmu_ibr_ctrl.SetAttribute("Deadband_lower_IqV", -0.05)
    fmu_ibr_ctrl.SetAttribute("Deadband_lower_IrU", -0.05)
    fmu_ibr_ctrl.SetAttribute("Deadband_lower_Pf", -0.0001)
    fmu_ibr_ctrl.SetAttribute("Deadband_lower_QV", -0.0001)
    fmu_ibr_ctrl.SetAttribute("Deadband_upper_IqV", 0.05)
    fmu_ibr_ctrl.SetAttribute("Deadband_upper_IrU", 0.05)
    fmu_ibr_ctrl.SetAttribute("Deadband_upper_Pf", 0.0001)
    fmu_ibr_ctrl.SetAttribute("Deadband_upper_QV", 0.0001)
    fmu_ibr_ctrl.SetAttribute("I_base", ibase)
    fmu_ibr_ctrl.SetAttribute("Imax", 1.2)  # pu
    fmu_ibr_ctrl.SetAttribute("IqV_FLAG", 1)
    fmu_ibr_ctrl.SetAttribute("IrV_FLAG", 1)
    fmu_ibr_ctrl.SetAttribute("Ki_CC_NS", ki_cc)
    fmu_ibr_ctrl.SetAttribute("Ki_CC_PS", ki_cc)
    fmu_ibr_ctrl.SetAttribute("Ki_P", 7.5)
    fmu_ibr_ctrl.SetAttribute("Ki_PLL", 5)
    fmu_ibr_ctrl.SetAttribute("Ki_Q", 7.5)
    fmu_ibr_ctrl.SetAttribute("Kp_CC_NS", kp_cc)
    fmu_ibr_ctrl.SetAttribute("Kp_CC_PS", kp_cc)
    fmu_ibr_ctrl.SetAttribute("Kp_IqV", 2)
    fmu_ibr_ctrl.SetAttribute("Kp_IrU", 5)
    fmu_ibr_ctrl.SetAttribute("Kp_P", 0.07)
    fmu_ibr_ctrl.SetAttribute("Kp_PLL", 5)
    fmu_ibr_ctrl.SetAttribute("Kp_Q", 0.07)
    fmu_ibr_ctrl.SetAttribute("Kp_QV", 2)
    fmu_ibr_ctrl.SetAttribute("LPF_DDSRF", 2*(2 * math.pi * fn))
    fmu_ibr_ctrl.SetAttribute("L_conv", lconv)
    fmu_ibr_ctrl.SetAttribute("P_FLAG", 2)
    fmu_ibr_ctrl.SetAttribute("Pf_FLAG", 1)
    fmu_ibr_ctrl.SetAttribute("Pf_lower_gain", 20)
    fmu_ibr_ctrl.SetAttribute("Pf_lower_limit", -0.2)
    fmu_ibr_ctrl.SetAttribute("Pf_upper_gain", 20)
    fmu_ibr_ctrl.SetAttribute("Pf_upper_limit", 0.2)
    # Phi_corr
    fmu_ibr_ctrl.SetAttribute("Pmax", 1)
    fmu_ibr_ctrl.SetAttribute("Pmin", -1)
    # Pn
    fmu_ibr_ctrl.SetAttribute("QV_FLAG", 1)
    fmu_ibr_ctrl.SetAttribute("Q_FLAG", 2)
    fmu_ibr_ctrl.SetAttribute("Qmax", 1)
    fmu_ibr_ctrl.SetAttribute("Qmin", -1)
    # Qn
    fmu_ibr_ctrl.SetAttribute("R_conv", trafo_r)
    fmu_ibr_ctrl.SetAttribute("Sn", sn * 1e6)  # VA
    fmu_ibr_ctrl.SetAttribute("T_IqV", 0.1e-3)  # s
    fmu_ibr_ctrl.SetAttribute("T_IrV", 0.1e-3)  # s
    fmu_ibr_ctrl.SetAttribute("T_P", 125e-3)  # s
    fmu_ibr_ctrl.SetAttribute("T_Pf", 20e-3)
    fmu_ibr_ctrl.SetAttribute("T_Pm", 20e-3)
    fmu_ibr_ctrl.SetAttribute("T_Q", 125e-3)  # s
    fmu_ibr_ctrl.SetAttribute("T_QV", 20e-3)
    fmu_ibr_ctrl.SetAttribute("T_Qm", 20e-3)
    # VLF
    # VLF_phi
    fmu_ibr_ctrl.SetAttribute("V_base", vbase)
    fmu_ibr_ctrl.SetAttribute("Z_base", zbase)
    fmu_ibr_ctrl.SetAttribute("dV_activate_IqV", 0.15)
    fmu_ibr_ctrl.SetAttribute("fn", fn)

    pf.WriteChangesToDb()
    pf.SetWriteCacheEnabled(0)



def build_pf_grid(pf, main_grid, grid_graph, vn, fn):
    # Initialize samplers
    ext_grid_sampler = ExternalGridSampler(pf, vn, fn)
    load_sampler = LoadSampler(pf, vn, fn)
    line_sampler = LineSampler(pf, vn, fn)
    topology_sampler = TopologySampler(pf, vn, fn)
    grounding_sampler = GroundingSampler(pf, vn, fn)

    active_project = pf.GetActiveProject()
    sc_main = active_project.GetContents('MainStudyCase.IntCase', 1)[0]
    main_nodes = list(grid_graph.nodes())

    for i, node in enumerate(main_nodes):
        bus = main_grid.CreateObject('ElmTerm', 'MainBus' + str(node))
        bus.uknom = vn
        if i == 0:
            create_slack(bus, node, vn, main_grid, ext_grid_sampler, grounding_sampler)
            continue

        connected_load = topology_sampler.is_load_connected()
        connected_source = topology_sampler.is_source_connected()
        source_type = topology_sampler.get_source_type()

        if connected_load:
            create_load(bus, node, main_grid, load_sampler, grounding_sampler)

        if connected_source:
            if source_type == "SYM":
                sync_machine_sampler = SynchronousMachineSampler(pf, vn, fn)
                create_generator(pf, bus, node, vn, fn, main_grid, sync_machine_sampler, grounding_sampler)
            elif source_type == "IBR":
                ibr_sampler = IBRSampler(pf, vn, fn)
                sn = ibr_sampler.get_sn()
                create_ibr(pf, bus, node, vn, fn, main_grid, sn)

    for edge in grid_graph.edges(keys=True):
        line = main_grid.CreateObject('ElmLne', 'MainLn_' + str(edge[0]) + '_' + str(edge[1]) + '_' + str(edge[2]))
        bus1 = main_grid.GetContents('MainBus{}.ElmTerm'.format(edge[0]), 1)[0]
        bus2 = main_grid.GetContents('MainBus{}.ElmTerm'.format(edge[1]), 1)[0]
        new_cubic1 = bus1.CreateObject('StaCubic', 'Cubicle')
        bus1.cubics.append(new_cubic1)
        new_cubic2 = bus2.CreateObject('StaCubic', 'Cubicle')
        bus2.cubics.append(new_cubic2)
        line.bus1 = new_cubic1
        line.bus2 = new_cubic2

        is_cable = line_sampler.is_cable()
        line.typ_id = line_sampler.get_line_typ(is_cable)

        line.dline = line_sampler.get_length(is_cable)
        line.i_dist = 1
        line.i_model = 2
        line.fd_model = 0
        line.ftau = fn
        line.fmin = 0.01
        line.fmax = 1000000
        line.FitParams()

    if vn >= 110:
        ibr_sampler = IBRSampler(pf, vn, fn)
        all_loads = main_grid.GetContents('*.ElmLod')
        all_generators = main_grid.GetContents('*.ElmSym')
        all_ibrs = main_grid.GetContents("*IBR*.ElmVac")
        psum_loads = sum(load.plini for load in all_loads)
        ssum_gens = get_generation_capacity(all_generators, all_ibrs)
        if ssum_gens > 0:
            power_share = get_generation_share(psum_loads, ssum_gens, load_sampler.get_locality_factor())
            for gen in all_generators:
                gen.pgini = gen.typ_id.sgn * power_share

            for ibr in all_ibrs:
                ibr.c_pmod.pelm[0].Pn = ibr.c_pmod.pelm[0].Sn * power_share
                ibr.p_phictrl.Psetp = -ibr.c_pmod.pelm[0].Sn * power_share / 1e6

                reactive_power_share = ibr_sampler.get_reactive_to_active_power_share() * power_share
                ibr.c_pmod.pelm[0].Qn = -ibr.c_pmod.pelm[0].Sn * reactive_power_share
                ibr.p_uctrl.Qsetp = ibr.c_pmod.pelm[0].Sn * reactive_power_share / 1e6

    elif vn == 20:
        all_ibrs = main_grid.GetContents("*IBR*.ElmVac")
        ibr_sampler = IBRSampler(pf, vn, fn)
        active_power_share = ibr_sampler.get_active_power_share()
        reactive_power_share = ibr_sampler.get_reactive_to_active_power_share() * active_power_share

        for ibr in all_ibrs:
            ibr.c_pmod.pelm[0].Pn = ibr.c_pmod.pelm[0].Sn * active_power_share
            ibr.p_phictrl.Psetp = -ibr.c_pmod.pelm[0].Sn * active_power_share / 1e6

            ibr.c_pmod.pelm[0].Qn = -ibr.c_pmod.pelm[0].Sn * reactive_power_share
            ibr.p_uctrl.Qsetp = ibr.c_pmod.pelm[0].Sn * reactive_power_share / 1e6

    else:
        raise NotImplementedError




    olddiagrams = active_project.GetContents("*.IntGrfnet", 1)
    for olddiagram in olddiagrams:
        olddiagram.Delete()
    drawer = sc_main.CreateObject('ComSgllayout', 'Layout')
    drawer.iGenType = 0
    drawer.pGrids = main_grid
    drawer.orthoType = 1
    drawer.Execute()

def check_dc_drift(res, number_of_rows, number_of_columns, period_length):
    """
    Rejects grids in which a current has a growing DC component in the last cycle of the initialisation run
    (util/dc_check.py, the post-processing applies the same check to every simulation before the event).
    """
    columns = [column for column in range(number_of_columns) if 'Isec' in res.GetVariable(column)]
    cycles = [[[res.GetValue(start + i, column)[1] for column in columns] for i in range(period_length)]
              for start in [number_of_rows - 2 * period_length, number_of_rows - period_length]]
    flagged, dc, dc_previous, ac = growing_dc(*cycles)
    for k in np.flatnonzero(flagged):
        print(f"Growing DC component at column {columns[k]} ({res.GetObject(columns[k]).loc_name}): {dc[k]:.3f} A "
              f"(previous cycle {dc_previous[k]:.3f} A), AC amplitude {ac[k]:.3f} A")
    return not flagged.any()


def check_grid_consistency(pf, fn, vn, debug, fs_export=9600):
    active_project = pf.GetActiveProject()
    load_flow = active_project.GetContents('*.ComLdf', 1)[0]
    lf_result = load_flow.Execute()
    if not lf_result == 0:
        print("Load Flow Failed")
        return False

    main_grid = active_project.GetContents('*Main*.ElmNet', 1)[0]
    lines = main_grid.GetContents("*.ElmLne")
    trafos = main_grid.GetContents("*.ElmTr2")
    syms = main_grid.GetContents("*.ElmSym")
    main_busses = main_grid.GetContents("*Main*.ElmTerm")

    for line in lines:
        if hasattr(line, "c:loading"):
            if not getattr(line, "c:loading") < 110:
                print("Line loading too high" + str(getattr(line, "c:loading")))
                return False
            pf.PrintPlain(getattr(line, "c:loading"))

    for trafo in trafos:
        if hasattr(trafo, "c:loading"):
            if not getattr(trafo, "c:loading") < 110:
                print("Trafo loading too high" + str(getattr(trafo, "c:loading")))
                return False
            pf.PrintPlain(getattr(trafo, "c:loading"))

    for sym in syms:
        if hasattr(sym, "c:loading"):
            if not getattr(sym, "c:loading") < 110:
                print("Sym loading too high" + str(getattr(sym, "c:loading")))
                return False
            pf.PrintPlain(getattr(sym, "c:loading"))

    for bus in main_busses:
        if hasattr(bus, "m:u1"):
            voltage_thresh = 0.1 if vn >= 110 else 0.05
            if not (1-voltage_thresh < getattr(bus, "m:u1") < 1+voltage_thresh):
                print("Bus voltage too high or low" + str(getattr(bus, "m:u1")))
                return False

    sc_main = active_project.GetContents('MainStudyCase.IntCase', 1)[0]
    inc = sc_main.GetContents('*.ComInc')[0]
    sim = sc_main.GetContents('*.ComSim')[0]
    if debug:
        sim.tstop = 0.1
    else:
        sim.tstop = 1.0

    inc_result = inc.Execute()
    if inc_result == 0 or inc_result == 1:
        sim_result = sim.Execute()
        if not sim_result == 0:
            print("Simulation failed")
            return False
    else:
        print("Initialization Failed")
        return False

    if debug:
        sim.tstop = 0.1
    else:
        sim.tstop = 1.5

    res = sc_main.GetContents('*EvemtResult.ElmRes')[0]
    res.Load()
    number_of_rows = res.GetNumberOfRows()
    number_of_columns = res.GetNumberOfColumns()
    period_length = int(1/fn * fs_export)

    if debug:
        tolerance = 0.05
    else:
        tolerance = 0.01

    # result columns 0 ... number_of_columns - 1 are the recorded variables, time is the default variable (not a column)
    for column in range(number_of_columns):
        if 'Isec' in res.GetVariable(column):
            last_period = [res.GetValue(number_of_rows - period_length + i, column)[1] for i in range(period_length)]
            if (max(last_period) - min(last_period)) / 2 < MIN_AC_AMPLITUDE_A:
                continue  # (nearly) zero current, e.g. a neutral-point current: the relative difference is only noise

        ierr, last_value = res.GetValue(number_of_rows - 1, column)
        ierr, previous_period_value = res.GetValue(number_of_rows - 1 - period_length, column)
        max_value = res.FindMaxInColumn(column)[1]

        if not abs(last_value - previous_period_value) / max_value < tolerance:
            print("Steady state not reached at column " + str(column) + " with difference of " + str(
                abs(last_value - previous_period_value) / max_value))
            print(res.GetObject(column))
            return False

    # not in debug mode: the 0.1 s initialisation run does not reach steady state
    if not debug and not check_dc_drift(res, number_of_rows, number_of_columns, period_length):
        return False

    print("======== Grid Okay =========")
    pf.PrintPlain("========= Grid Okay =========")
    return True

def generate_grid_topology(pf, vn, fn, debug, dtemt=1e-5, fs_export=9600):
    active_project = pf.GetActiveProject()
    main_grid = active_project.GetContents('*Main*.ElmNet', 1)[0]
    grid_graph = generate_hv_topology_graph() if vn >= 110 else generate_mv_topology_graph(vn)
    build_pf_grid(pf, main_grid, grid_graph, vn, fn)
    prepare_model(pf, debug=debug, dtemt=dtemt, fs_export=fs_export)
    grid_okay = check_grid_consistency(pf, fn, vn, debug, fs_export=fs_export)

    return grid_okay

if __name__ == '__main__':
    import powerfactory

    pf = powerfactory.GetApplicationExt()
    # generate_grid_topology(pf, 345, 60)
    generate_grid_topology(pf, 110, 50)
    # generate_grid_topology(pf, 20, 50)