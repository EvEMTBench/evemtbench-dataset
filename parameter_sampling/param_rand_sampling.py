import math

import networkx as nx
import numpy as np

np.random.seed(0)


def generate_hv_topology_graph():
    max_degree = 5
    num_nodes = int(np.random.uniform(4, 20))
    num_edges = int(np.random.uniform(num_nodes * 1.2, num_nodes * 1.6))

    # networkx uses its own random generator, so it gets a seed from the numpy stream to keep the topologies reproducible
    generated_graph = nx.gnm_random_graph(num_nodes, num_edges, seed=np.random.randint(2**31 - 1))
    generated_graph = nx.MultiGraph(generated_graph)

    nodes_to_adjust = [node for node in generated_graph.nodes() if generated_graph.degree[node] > max_degree]
    while nodes_to_adjust:
        for node in nodes_to_adjust:
            while generated_graph.degree[node] > max_degree:
                neighbors = list(generated_graph.neighbors(node))
                if neighbors:
                    generated_graph.remove_edge(node, np.random.choice(neighbors))
        nodes_to_adjust = [node for node in generated_graph.nodes() if generated_graph.degree[node] > max_degree]

    if not nx.is_connected(generated_graph):
        components = list(nx.connected_components(generated_graph))
        while len(components) > 1:
            a = np.random.choice(list(components[0]))
            b = np.random.choice(list(components[1]))
            generated_graph.add_edge(a, b)
            components = list(nx.connected_components(generated_graph))

    for _ in range(2):
        # parallel lines
        valid_edges = [(u, v) for u, v in generated_graph.edges()
                       if generated_graph.degree[u] < max_degree and generated_graph.degree[v] < max_degree]
        if valid_edges:
            edge = valid_edges[np.random.randint(len(valid_edges))]
            generated_graph.add_edge(*edge)

    return generated_graph


def generate_mv_topology_graph(voltage_level):
    assert voltage_level == 20
    G = nx.Graph()
    G.add_node(0)

    n_feeders = np.random.randint(1, 6)
    current_node = 1
    feeders = []

    for _ in range(n_feeders):
        n_buses = np.random.randint(1, 6)
        feeder_nodes = []
        for j in range(n_buses):
            node_id = current_node
            current_node += 1
            feeder_nodes.append(node_id)
            G.add_node(node_id)
            if j == 0:
                G.add_edge(0, node_id)
            else:
                G.add_edge(feeder_nodes[j - 1], node_id)
        feeders.append(feeder_nodes)

    for feeder in feeders:
        n_laterals = np.random.randint(0, 3)
        for _ in range(n_laterals):
            attach_node = np.random.choice(feeder)
            n_lateral_buses = np.random.randint(1, 3)
            lateral_nodes = []
            for j in range(n_lateral_buses):
                node_id = current_node
                current_node += 1
                lateral_nodes.append(node_id)
                G.add_node(node_id)
                if j == 0:
                    G.add_edge(attach_node, node_id)
                else:
                    G.add_edge(lateral_nodes[j - 1], node_id)

    if n_feeders >= 2:
        idx1, idx2 = np.random.choice(len(feeders), 2, replace=False)
        last_node1 = feeders[idx1][-1]
        last_node2 = feeders[idx2][-1]
        G.add_edge(last_node1, last_node2)

    return nx.MultiGraph(G)


class TopologySampler(object):
    def __init__(self, pf, vn, fn):
        self.pf = pf
        self.vn = vn
        self.fn = fn

    def is_load_connected(self):
        return np.random.choice([True, False]) if self.vn >= 110 else True

    def is_source_connected(self):
        return np.random.choice([True, False]) if self.vn >= 110 else np.random.choice([True, False], p=[0.2, 0.8])

    def get_source_type(self):
        if self.vn == 345:
            return "SYM"
        elif self.vn == 110:
            return np.random.choice(["SYM", "IBR"])
        else:
            return "IBR"


class SynchronousMachineSampler(object):
    def __init__(self, pf, vn, fn):
        self.pf = pf
        self.vn = vn
        self.fn = fn

        if vn >=110:
            self.sym_lib = pf.GetCurrentUser().GetContents(f"*CustomTypeLib*")[0].GetContents("*SymTypes*")[0].GetContents(f"*{vn}kV*")[0]
            self.sym_trafo_lib = pf.GetCurrentUser().GetContents(f"*CustomTypeLib*")[0].GetContents("*TrafoTypes*")[0].GetContents(f"*{fn}*")[0].GetContents(f"MachineTrafos")[0]
        else:
            raise NotImplementedError

        self.syms = self.sym_lib.GetContents('*.TypSym*')
        self.sym_trafos = self.sym_trafo_lib.GetContents('*.TypTr2*')

    def get_sym_typ(self):
        return np.random.choice(self.syms)

    def get_sym_trafo_type(self, gen):
        trafo_type = np.random.choice(self.sym_trafos)
        if not (
                trafo_type.strn >= gen.typ_id.sgn and trafo_type.utrn_l == gen.typ_id.ugn and trafo_type.utrn_h == self.vn):
            trafo_type = self.get_sym_trafo_type(gen)
        return trafo_type

    def get_usetp(self):
        return np.random.uniform(0.98, 1.02)



class SwitchTrafoSampler(object):
    def __init__(self, pf, vn, fn):
        self.pf = pf
        self.vn = vn
        self.fn = fn

        parent_lib = pf.GetCurrentUser().GetContents(f"*CustomTypeLib*")[0]
        if vn == 345:
            self.trafo_to_lv_lib = parent_lib.GetContents("*TrafoTypes*")[0].GetContents(f"*{fn}*")[0].GetContents(f"*GridTrafos*")[0].GetContents(f"*{vn}/*")[0]
        else:
            self.trafo_to_hv_lib = parent_lib.GetContents("*TrafoTypes*")[0].GetContents(f"*{fn}*")[0].GetContents(f"*GridTrafos*")[0].GetContents(f"*/{vn}*")[0]
            if vn == 110:
                self.trafo_to_lv_lib = parent_lib.GetContents("*TrafoTypes*")[0].GetContents(f"*{fn}*")[0].GetContents(f"*GridTrafos*")[0].GetContents(f"*{vn}/20*")[0]
            else:
                self.trafo_to_lv_lib = parent_lib.GetContents("*TrafoTypes*")[0].GetContents(f"*{fn}*")[0].GetContents(f"*GridTrafos*")[0].GetContents(f"*{vn}/*")[0]

        self.trafos_to_lv = self.trafo_to_lv_lib.GetContents("*.TypTr2")
        if not vn == 345:
            self.trafos_to_hv = self.trafo_to_hv_lib.GetContents("*.TypTr2")


    def get_trafo_to_hv(self):
        return np.random.choice(self.trafos_to_hv)

    def get_trafo_to_lv(self):
        return np.random.choice(self.trafos_to_lv)


class ExciterSampler(object):
    def __init__(self, pf, vn, fn):
        self.pf = pf
        self.vn = vn
        self.fn = fn

    def get_Tb(self):
        return 0 * np.random.uniform(0.9, 1.1)

    def get_Tc(self):
        return 0 * np.random.uniform(0.9, 1.1)

    def get_Tr(self):
        return 0 * np.random.uniform(0.9, 1.1)

    def get_Ka(self):
        return 400 * np.random.uniform(0.9, 1.1)

    def get_Ta(self):
        return 0.02 * np.random.uniform(0.9, 1.1)

    def get_Kf(self):
        return 0.03 * np.random.uniform(0.9, 1.1)

    def get_Tf(self):
        return 1 * np.random.uniform(0.9, 1.1)

    def get_Te(self):
        return 0.8 * np.random.uniform(0.9, 1.1)

    def get_Kc(self):
        return 0.2 * np.random.uniform(0.9, 1.1)

    def get_Ke(self):
        return 1 * np.random.uniform(0.9, 1.1)

    def get_Kd(self):
        return 0.38 * np.random.uniform(0.9, 1.1)

    def get_E1(self):
        return 3.14 * np.random.uniform(0.9, 1.1)

    def get_SE1(self):
        return 0.03 * np.random.uniform(0.9, 1.1)

    def get_E2(self):
        return 4.18 * np.random.uniform(0.9, 1.1)

    def get_SE2(self):
        return 0.1 * np.random.uniform(0.9, 1.1)

    def get_Vamin(self):
        return -14.5 * np.random.uniform(0.9, 1.1)

    def get_Vrmin(self):
        return -999

    def get_Vamax(self):
        return 14.5 * np.random.uniform(0.9, 1.1)

    def get_Vrmax(self):
        return 999


class IBRSampler(object):
    def __init__(self, pf, vn, fn):
        self.pf = pf
        self.vn = vn
        self.fn = fn

    def get_sn(self):
        if self.vn == 20:
            return np.random.uniform(1, 15)
        elif self.vn == 110:
            return np.random.uniform(20, 50)
        else:
            raise NotImplementedError

    def get_active_power_share(self):
        return np.random.uniform(0.1, 0.9)

    def get_reactive_to_active_power_share(self):
        return np.random.uniform(0.05, 0.10)


class ExternalGridSampler(object):
    def __init__(self, pf, vn, fn):
        self.pf = pf
        self.vn = vn
        self.fn = fn
        if vn == 110:
            ext_grid_trafo_lib = \
            pf.GetCurrentUser().GetContents(f"*CustomTypeLib*")[0].GetContents("*TrafoTypes*")[0].GetContents(f"*{fn}*")[0].GetContents(f"*GridTrafos*")[
                0].GetContents(f"380/110*")[0]
            self.ext_grid_trafo_lib = ext_grid_trafo_lib
            self.trafo_types = self.ext_grid_trafo_lib.GetContents('*.TypTr2*')
        elif vn == 20:
            ext_grid_trafo_lib = \
            pf.GetCurrentUser().GetContents(f"*CustomTypeLib*")[0].GetContents("*TrafoTypes*")[0].GetContents(f"*{fn}*")[0].GetContents(f"*GridTrafos*")[
                0].GetContents(f"110/20*")[0]
            self.ext_grid_trafo_lib = ext_grid_trafo_lib
            self.trafo_types = self.ext_grid_trafo_lib.GetContents('*.TypTr2*')
        else:
            self.ext_grid_trafo_lib = None

    def get_ext_grid_trafo_type(self):
        trafo_type = np.random.choice(self.trafo_types)
        required_strn = 500 if self.vn == 110 else 80
        if trafo_type.strn != required_strn:
            return self.get_ext_grid_trafo_type()
        return trafo_type

    def get_sn(self):
        if self.vn == 345 or self.vn == 110:
            # both supplied by 380/345 EHV grids
            return np.random.uniform(10000, 53000)
        elif self.vn == 20:
            # supplied by overlaying 110 kV Grid
            return np.random.uniform(800, 8000)
        else:
            raise NotImplementedError

    def get_rntxn(self):
        return np.random.uniform(0.1, 0.2)

    def get_x0tx1(self):
        return np.random.uniform(2, 4)

    def get_r0tx0(self):
        return np.random.uniform(0.1, 0.2)

    def get_usetp(self):
        return np.random.uniform(0.98, 1.02)

    def get_phiini(self):
        return np.random.uniform(-180, 180)

class LoadSampler(object):
    def __init__(self, pf, vn, fn):
        self.pf = pf
        self.vn = vn
        self.fn = fn

        user = pf.GetCurrentUser()
        parent_lib = user.GetContents(f"*CustomTypeLib*")[0]
        self.load_lib = parent_lib.GetContents("*LoadTypes*")[0]
        self.load_trafo_lib = parent_lib.GetContents("*TrafoTypes*")[0].GetContents(f"*{fn}*")[0].GetContents(f"*GridTrafos*")[0].GetContents(f"*{vn}/*")[0]

        self.load_trafos = self.load_trafo_lib.GetContents('*.TypTr2*')
        self.load_types = self.load_lib.GetContents('*.TypLod')

    def get_load_type(self):
        return np.random.choice(self.load_types)

    def get_load_trafo_type(self, loadp, loadq):
        trafo_type = np.random.choice(self.load_trafos)

        load_s = math.sqrt(loadp ** 2 + loadq ** 2)
        if not (trafo_type.strn >= load_s):
            trafo_type = self.get_load_trafo_type(loadp, loadq)
        return trafo_type

    def get_pq(self):
        if self.vn == 345:
            return np.random.uniform(9, 326), np.random.uniform(3.6, 116)
        elif self.vn == 110:
            return np.random.uniform(0, 31), np.random.uniform(0, 12.5)
        elif self.vn == 20:
            sn = np.random.uniform(0.1, 1.6)
            pf = np.random.uniform(0.8, 1.05)
            if pf > 1:
                cosphi = 2 - pf
                is_inductive = False
            else:
                cosphi = pf
                is_inductive = True

            p = sn * cosphi
            q = math.sqrt(sn**2 - p**2) * (1 if is_inductive else -1)
            return p, q
        else:
            raise NotImplementedError

    def get_load_scaling_factor(self):
        return np.random.uniform(0.5, 1.5)

    def get_locality_factor(self):
        # 90 - 120% are supplied by local generation, the rest by the external grid.
        return np.random.uniform(0.9, 1.2)


MAX_GENERATION_SHARE = 0.9  # local generation is dispatched at most at 90 % of its rated power


def get_dispatchable_generators(generators):
    # Synchronous machines of 5000 MVA or more are grid equivalents (e.g. G1 of the IEEE 39-bus system) and keep their setpoint
    return [gen for gen in generators if gen.typ_id.sgn < 5000]


def get_generation_capacity(generators, ibrs):
    """Rated power in MVA of all dispatchable local generation (synchronous machines and IBRs)."""
    return (sum(gen.typ_id.sgn for gen in get_dispatchable_generators(generators))
            + sum(ibr.c_pmod.pelm[0].Sn / 1e6 for ibr in ibrs))


def get_generation_share(psum_loads, ssum_gens, locality_factor):
    """Share of the rated power at which all local generation is dispatched, so that it supplies locality_factor
    times the total load, limited to MAX_GENERATION_SHARE."""
    return min((psum_loads / ssum_gens) * locality_factor, MAX_GENERATION_SHARE)


class MotorSampler(object):
    def __init__(self, pf, vn, fn):
        self.pf = pf
        self.vn = vn
        self.fn = fn

        user = pf.GetCurrentUser()
        parent_lib = user.GetContents(f"*CustomTypeLib*")[0]
        if vn == 110:
            self.motor_lib = parent_lib.GetContents("*AsymTypes*")[0].GetContents(f"*11kV*")[0]
            self.motor_trafo_lib = parent_lib.GetContents("*TrafoTypes*")[0].GetContents(f"*{fn}*")[0].GetContents(f"*GridTrafos*")[0].GetContents(f"*110/11kV*")[0]
        elif vn == 20:
            self.motor_lib = parent_lib.GetContents("*AsymTypes*")[0].GetContents(f"*0_4kV*")[0]
            self.motor_trafo_lib = parent_lib.GetContents("*TrafoTypes*")[0].GetContents(f"*{fn}*")[0].GetContents(f"*GridTrafos*")[0].GetContents(f"*20/0_4kV*")[0]
        else:
            raise NotImplementedError

        self.motor_types = self.motor_lib.GetContents("*.TypAsmo")
        self.motor_trafo_types = self.motor_trafo_lib.GetContents("*.TypTr2")

    def get_motor_type(self):
        return np.random.choice(self.motor_types)

    def get_motor_trafo_type(self):
        return np.random.choice(self.motor_trafo_types)


class LineSampler(object):
    def __init__(self, pf, vn, fn):
        self.pf = pf
        self.vn = vn
        self.fn = fn
        user = pf.GetCurrentUser()
        parent_lib = user.GetContents(f"*CustomTypeLib*")[0]
        self.line_lib = parent_lib.GetContents("*OHLTypes*")[0].GetContents(f"*{fn}*")[0].GetContents(f"*{vn}kV*")[0]
        self.cable_lib = parent_lib.GetContents("*Cables*")[0].GetContents(f"*20kV*")[0]

        self.typ_tows = self.line_lib.GetContents("*.TypTow")
        self.typ_cables = self.cable_lib.GetContents("*.TypCabsys")

    def is_cable(self):
        return np.random.choice([True, False], p=[0.7, 0.3])

    def get_line_typ(self, is_cable):
        if self.vn >= 110:
            return np.random.choice(self.typ_tows)
        else:
            if is_cable:
                return np.random.choice(self.typ_cables)
            else:
                return np.random.choice(self.typ_tows)

    def get_length(self, is_cable=False):
        if self.vn == 345:
            return np.random.uniform(1, 111)
        elif self.vn == 110:
            return np.random.uniform(1, 32)
        elif self.vn == 20:
            if is_cable:
                # cable
                return np.random.uniform(0.1, 0.75) * 5
            else:
                # ohl
                return np.random.uniform(0.1, 1.9) * 5
        else:
            raise NotImplementedError


class GroundingSampler(object):
    def __init__(self, pf, vn, fn):
        self.pf = pf
        self.vn = vn
        self.fn = fn

    def get_grnd_type(self):
        if self.vn == 20:
            return np.random.choice(["solid", "resonant", "resistive"])
        elif self.vn == 110:
            return np.random.choice(["solid", "resonant", "resistive"])
        else:
            return "solid"

    def get_coil_tuning(self):
        # Typical value of coil tuning in ampere
        return np.random.uniform(-10, 10)

    def get_solid_resistance(self):
        # Typical value of directly grounded systems
        return np.random.uniform(0.1, 2)

    def get_resistive_ground_resistance(self):
        if self.vn == 20:
            return np.random.uniform(5.77, 9.62)
        elif self.vn == 110:
            return np.random.uniform(6.35, 31.75)
        else:
            return -1

    def get_parasitic_resistance_percentage(self):
        # Typical value of parasitic resistance current in % of petersen coil current
        return np.random.uniform(2, 3)


class ArcSampler(object):
    def __init__(self, pf, vn, fn):
        self.pf = pf
        self.vn = vn
        self.fn = fn

    def get_tau(self, is_cable):
        if is_cable:
            return np.random.uniform(0.05, 0.4) * 1e-3
        elif self.vn == 20:
            return np.random.uniform(0.05, 0.65) * 1e-3
        elif self.vn == 110:
            return np.random.uniform(0.3, 1.2) * 1e-3
        elif self.vn == 345:
            return np.random.uniform(0.3, 1.2) * 1e-3
        else:
            raise NotImplementedError

    def get_u0(self, is_cable):
        if is_cable:
            return np.random.uniform(300, 4000)
        elif self.vn == 20:
            return np.random.uniform(535, 1075)
        elif self.vn == 110:
            return np.random.uniform(2200, 5800)
        elif self.vn == 345:
            return np.random.uniform(4900, 13900)
        else:
            raise NotImplementedError

    def get_r0(self, is_cable):
        if is_cable:
            return np.random.uniform(0, 0.015)
        elif self.vn == 20:
            return np.random.uniform(0.014, 0.038)
        elif self.vn == 110:
            return np.random.uniform(0.088, 0.248)
        elif self.vn == 345:
            return np.random.uniform(0.208, 0.608)
        else:
            raise NotImplementedError

class EventSampler(object):
    def __init__(self, pf, vn, fn, main_grid, debug):
        self.pf = pf
        self.vn = vn
        self.fn = fn
        self.debug = debug
        self.mv_events = [
            "switch_inrushLV",
            "switch_inrushHV",
            "switch_load_on",
            "switch_load_off",
            "switch_cap_on",
            "switch_cap_off",
            "switch_ohl_on",
            "switch_ohl_off",
            "switch_cable_on",
            "switch_cable_off",
            "switch_motor_start",
            "switch_ibr_trip",

            "flt_1phg_shc",
            "flt_1phg_shc_w_arc",
            "flt_2ph_shc",
            "flt_2phg_shc",
            "flt_3ph_shc",
            "flt_1phg_hif",
            "flt_1phg_hif_w_arc",

            "flt_1phg_incipient",
            "flt_1phg_incipient_w_arc",
        ]

        self.hv_events = [
            "switch_inrushLV",
            "switch_inrushHV",
            "switch_load_on",
            "switch_load_off",
            "switch_cap_on",
            "switch_cap_off",
            "switch_ohl_on",
            "switch_ohl_off",
            "switch_ibr_trip",
            "switch_gen_trip",

            "flt_1phg_shc",
            "flt_1phg_shc_w_arc",
            "flt_2ph_shc",
            "flt_2phg_shc",
            "flt_3ph_shc",

            "flt_1phg_incipient",
            "flt_1phg_incipient_w_arc",
        ]

        self.ehv_events = [
            "switch_inrushLV",
            "switch_load_on",
            "switch_load_off",
            "switch_cap_on",
            "switch_cap_off",
            "switch_ohl_on",
            "switch_ohl_off",
            "switch_gen_trip",

            "flt_1phg_shc",
            "flt_1phg_shc_w_arc",
            "flt_2ph_shc",
            "flt_2phg_shc",
            "flt_3ph_shc",

            "flt_1phg_incipient",
            "flt_1phg_incipient_w_arc",
        ]

        if main_grid is not None:
            self.elm_syms = main_grid.GetContents('*.ElmSym')
            self.elm_vacs = main_grid.GetContents('*IBR*.ElmVac')

            self.main_lines = main_grid.GetContents('*Main*.ElmLne')
            self.main_busses = main_grid.GetContents('*Main*.ElmTerm')

    def get_event_type(self):
        if self.vn == 20:
            event_type = np.random.choice(self.mv_events)
        elif self.vn == 110:
            event_type = np.random.choice(self.hv_events)
        elif self.vn == 345:
            event_type = np.random.choice(self.ehv_events)
        else:
            raise NotImplementedError

        if "switch_gen_trip" == event_type:
            if len(self.elm_syms) < 1:
                event_type = self.get_event_type()
        if "switch_ibr_trip" == event_type:
            if len(self.elm_vacs) < 1:
                event_type = self.get_event_type()
        return event_type

    def get_event_start(self):
        if self.debug:
            return np.random.uniform(0.02, 0.05)
        else:
            return 1.0 + np.random.uniform(0.1, 0.3)

    def get_target(self, event_type):
        if "switch" in event_type:
            if "switch_gen_trip" == event_type:
                def select_gen():
                    selected_gen = np.random.choice(self.elm_syms)
                    if selected_gen.typ_id.ugn == self.vn:
                        selected_gen = select_gen()
                        return selected_gen
                    else:
                        return selected_gen
                main_bus = select_gen().bus1.cterm.GetNextHVBus()
                return main_bus
            elif "switch_ibr_trip" == event_type:
                selected_ibr = np.random.choice(self.elm_vacs)
                main_bus = selected_ibr.p_uctrl.p_cub.cterm
                return main_bus
            else:
                return np.random.choice(self.main_busses)
        else:
            target_type = np.random.choice(["bus", "line"], p=[0.2, 0.8])
            if target_type == "bus":
                return np.random.choice(self.main_busses)
            elif target_type == "line":
                return np.random.choice(self.main_lines)
            else:
                raise ValueError("Invalid target")

    def get_flt_target_line_location(self):
        return np.random.uniform(1, 99)

    def get_shc_resistance(self):
        # Approximate resistances of short circuits
        return np.random.uniform(0.001, 50)

    def get_hif_resistance(self):
        # high impedance ground faults like wooden poles or trees can have extremely large resistances
        # Modeling and Experimental Verification of High Impedance Arcing Fault in Medium Voltage Networks
        impedance_level = np.random.choice([1, 2, 3, 4])
        if impedance_level == 1:
            hif_resistance = np.random.uniform(50, 500)
        elif impedance_level == 2:
            hif_resistance = np.random.uniform(500, 5000)
        elif impedance_level == 3:
            hif_resistance = np.random.uniform(5000, 50000)
        elif impedance_level == 4:
            hif_resistance = np.random.uniform(50000, 150000)
        else:
            raise ValueError("Invalid impedance level")
        return hif_resistance

    def get_phase_2ph(self):
        return np.random.choice(['ab', 'bc', 'ca'])

    def get_phase_1ph(self):
        return np.random.choice(['a', 'b', 'c'])

    def get_iflt_duration(self):
        period_time = 1/self.fn
        return np.random.uniform(0.1 * period_time, 4 * period_time)


class CapacitanceSampler(object):
    def __init__(self, pf, vn, fn):
        self.pf = pf
        self.vn = vn
        self.fn = fn

    def get_cap_power(self):
        if self.vn == 20:
            return np.random.uniform(0.3, 2.4)
        elif self.vn == 110 or self.vn == 345:
            return np.random.uniform(60, 200)
        else:
            raise NotImplementedError
