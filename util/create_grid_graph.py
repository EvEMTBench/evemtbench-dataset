import pickle

import networkx as nx


def create_graph_from_existing_grid(main_grid):
    grid_graph = nx.MultiGraph()

    # Add buses as nodes
    for i, bus in enumerate(main_grid.GetContents('*.ElmTerm', 1)):
        grid_graph.add_node(bus.loc_name)

    # Add lines as edges
    for i, line in enumerate(main_grid.GetContents('*.ElmLne', 1)):
        node1 = line.bus1.cterm.loc_name
        node2 = line.bus2.cterm.loc_name
        key = line.loc_name
        grid_graph.add_edge(node1, node2, key=key)

        typ_id = line.typ_id

        param_dict = {
            'length': line.dline,
            'xline': line.X1/line.dline,
            'rline': line.R1/line.dline,
            'xline0': line.X0/line.dline,
            'rline0': line.R0/line.dline,
            'bus_1': node1,  # terminal i, fault locations are given relative to this bus
            'bus_2': node2,
            'cubicle_1': line.bus1.loc_name,
            'cubicle_2': line.bus2.loc_name,
            'line_type': typ_id.loc_name if typ_id else None,
            'i_dist': line.i_dist,
            'i_model': line.i_model,
            'fd_model': line.fd_model,
            'ftau': line.ftau,
            'fmin': line.fmin,
            'fmax': line.fmax,
        }

        grid_graph.edges[(node1, node2, key)][f'{key}_param_dict'] = param_dict

        # Add line type parameters if a line type is assigned
        line_type = typ_id
        line_type_key = f"{key}_typ_param_dict"
            
        # Extract line type parameters - handle different types explicitly
        typ_param_dict = {}
        
        # Add line type name for reference
        typ_param_dict['line_type_name'] = line_type.loc_name
        
        # Check the specific type and extract parameters accordingly
        type_name = line_type.GetClassName()
        
        if type_name == 'TypTow':  # Overhead line type
            typ_param_dict['line_type_category'] = 'Overhead'
            typ_param_dict['line_type_specific'] = 'TypTow'
            
            # Extract OHL-specific parameters
            typ_param_dict['nlcir'] = line_type.nlcir
            typ_param_dict['nlear'] = line_type.nlear
            typ_param_dict['iTransMode'] = line_type.iTransMode
            typ_param_dict['gshunt'] = line_type.gshunt
            typ_param_dict['rearth'] = line_type.rearth

            # Conductor information - convert to string names for pickling
            if line_type.pcond_c:
                typ_param_dict['pcond_c'] = [cond.loc_name for cond in line_type.pcond_c]
            else:
                typ_param_dict['pcond_c'] = []

            if line_type.pcond_e:
                typ_param_dict['pcond_e'] = [cond.loc_name for cond in line_type.pcond_e]
            else:
                typ_param_dict['pcond_e'] = []

            # Geometry parameters
            typ_param_dict['xy_c'] = line_type.xy_c
            typ_param_dict['xy_e'] = line_type.xy_e
            
            # Differentiate between cable and overhead line
            is_cable = 'Cable' in line_type.loc_name or 'cable' in line_type.loc_name.lower()
            is_ohl = any(arrangement in line_type.loc_name for arrangement in
                         ['flat', 'vertical', 'danube', 'fork', 'stower', 'flat2e', 'Tower'])

            typ_param_dict['is_cable'] = is_cable
            typ_param_dict['is_ohl'] = is_ohl
            typ_param_dict['line_category'] = 'Cable' if is_cable else 'Overhead'

            # Extract tower arrangement from name if possible
            arrangement_patterns = ['flat', 'vertical', 'danube', 'fork', 'stower', 'flat2e']
            for pattern in arrangement_patterns:
                if pattern in line_type.loc_name.lower():
                    typ_param_dict['tower_arrangement'] = pattern
                    break
            else:
                typ_param_dict['tower_arrangement'] = 'unknown'

        elif type_name == 'TypCabsys':  # Cable system type
            typ_param_dict['line_type_category'] = 'Cable'
            typ_param_dict['line_type_specific'] = 'TypCabsys'
            
            # Extract cable-specific parameters
            # Add basic cable identification
            is_cable = True
            typ_param_dict['is_cable'] = is_cable
            typ_param_dict['line_category'] = 'Cable'
            
            # Add cable-specific parameters if available
            if hasattr(line_type, 'ncable'):
                typ_param_dict['ncable'] = line_type.ncable
            if hasattr(line_type, 'cable_type'):
                typ_param_dict['cable_type'] = line_type.cable_type

        elif type_name == 'TypLne':  # General line type
            typ_param_dict['line_type_category'] = 'General'
            typ_param_dict['line_type_specific'] = 'TypLne'
            
            # Extract general line parameters
            # Differentiate between cable and overhead line based on name
            is_cable = 'Cable' in line_type.loc_name or 'cable' in line_type.loc_name.lower()
            typ_param_dict['is_cable'] = is_cable
            typ_param_dict['line_category'] = 'Cable' if is_cable else 'Overhead'

            # Extract line impedance parameters
            typ_param_dict['rline'] = line_type.rline
            typ_param_dict['xline'] = line_type.xline
            typ_param_dict['cline'] = line_type.cline
            typ_param_dict['rline0'] = line_type.rline0
            typ_param_dict['xline0'] = line_type.xline0
            typ_param_dict['cline0'] = line_type.cline0


        else:
            # Unknown line type - fail loud
            raise AttributeError(f"ERROR: Unknown line type {type_name} for {line_type.loc_name}. Expected TypTow, TypCabsys, or TypLne.")

        grid_graph.edges[(node1, node2, key)][line_type_key] = typ_param_dict

    # Add transformers as edges
    for i, trafo in enumerate(main_grid.GetContents('*.ElmTr2', 1)):
        node1 = trafo.bushv.cterm.loc_name
        node2 = trafo.buslv.cterm.loc_name
        key = trafo.loc_name

        grid_graph.add_edge(node1, node2, key=key)

        typ_id = trafo.typ_id

        param_dict = {
            'name': key,
            'bus_1': node1,  # HV side
            'bus_2': node2,  # LV side
            'cubicle_1': trafo.bushv.loc_name,
            'cubicle_2': trafo.buslv.loc_name,
            'trafo_type': typ_id.loc_name,
            'cgnd_h': trafo.cgnd_h,
            'cgnd_l': trafo.cgnd_l,
            're0tr_h': trafo.re0tr_h,
            're0tr_l': trafo.re0tr_l,
        }
        grid_graph.edges[(node1, node2, key)][f'{key}_param_dict'] = param_dict


        trafo_type = typ_id
        trafo_type_key = f"{key}_typ_param_dict"

        # Extract transformer type parameters with explicit error handling
        typ_param_dict = {
            'strn': trafo_type.strn,
            'frnom': trafo_type.frnom,
            'utrn_h': trafo_type.utrn_h,
            'utrn_l': trafo_type.utrn_l,
            'tr2cn_h': trafo_type.tr2cn_h,
            'tr2cn_l': trafo_type.tr2cn_l,
            'nt2ag': trafo_type.nt2ag,
            'uktr': trafo_type.uktr,
            'pcutr': trafo_type.pcutr,
            'curmg': trafo_type.curmg,
            'pfe': trafo_type.pfe,
            'x0pu': trafo_type.x0pu,
            'r0pu': trafo_type.r0pu,
            'iLimb': trafo_type.iLimb,
            'itapch': trafo_type.itapch,
            'itrmt': trafo_type.itrmt,
            'satcur': trafo_type.satcur,
            'satflux': trafo_type.satflux,
            'iInterPol': trafo_type.iInterPol,
            'smoothfac': trafo_type.smoothfac,
            'zx0hl_n': trafo_type.zx0hl_n if hasattr(trafo_type, 'zx0hl_n') else None,
            'rtox0_n': trafo_type.rtox0_n if hasattr(trafo_type, 'rtox0_n') else None,
            'trafo_type_name': trafo_type.loc_name,
        }
        grid_graph.edges[(node1, node2, key)][trafo_type_key] = typ_param_dict

    # Add loads as node parameters
    for i, load in enumerate(main_grid.GetContents('*.ElmLod', 1)):
        node_name = load.bus1.cterm.loc_name
        key = load.loc_name

        # Basic load parameters
        param_dict = {
            'p': load.plini,
            'q': load.qlini,
            'load_type': load.typ_id.loc_name if load.typ_id else None,
            'mode_inp': load.mode_inp,
        }
        grid_graph.nodes[node_name][f'{key}_param_dict'] = param_dict

        # Add load type parameters if a load type is assigned
        if load.typ_id:
            load_type = load.typ_id
            load_type_key = f"{key}_typ_param_dict"
            
            # Extract load type parameters with explicit attribute checking
            typ_param_dict = {}

            typ_param_dict['kpu0'] = load_type.kpu0
            typ_param_dict['kpu1'] = load_type.kpu1
            typ_param_dict['kpu'] = load_type.kpu
            typ_param_dict['kqu0'] = load_type.kqu0
            typ_param_dict['kqu1'] = load_type.kqu1
            typ_param_dict['kqu'] = load_type.kqu

            typ_param_dict['aP'] = load_type.aP
            typ_param_dict['bP'] = load_type.bP
            typ_param_dict['cP'] = load_type.cP
            typ_param_dict['aQ'] = load_type.aQ
            typ_param_dict['bQ'] = load_type.bQ
            typ_param_dict['cQ'] = load_type.cQ
            
            grid_graph.nodes[node_name][load_type_key] = typ_param_dict

    # Add generators as node parameters
    for i, gen in enumerate(main_grid.GetContents('*.ElmSym', 1)):
        node_name = gen.bus1.cterm.loc_name
        key = gen.loc_name

        param_dict = {
            'p': gen.pgini,
            'q': gen.qgini,
            'usetp': gen.usetp,
            'phisetp': gen.phiini,
            'sgn': gen.typ_id.sgn if gen.typ_id else None,
            'ugn': gen.typ_id.ugn if gen.typ_id else None,
            'gen_type': gen.typ_id.loc_name if gen.typ_id else None,
            'iqtype': gen.iqtype,
            'Pmax_uc': gen.Pmax_uc,
            'av_mode': gen.av_mode,
        }
        grid_graph.nodes[node_name][f'{key}_param_dict'] = param_dict

        # Add synchronous machine type parameters if a type is assigned
        if gen.typ_id:
            sym_type = gen.typ_id
            sym_type_key = f"{key}_typ_param_dict"
            
            # Extract synchronous machine type parameters with explicit error handling
            typ_param_dict = {}
            
            # Basic parameters
            typ_param_dict['iturbo'] = sym_type.iturbo
            typ_param_dict['sgn'] = sym_type.sgn
            typ_param_dict['cosn'] = sym_type.cosn
            typ_param_dict['ugn'] = sym_type.ugn
            
            # Reactance parameters
            typ_param_dict['xdss'] = sym_type.xdss
            typ_param_dict['xqss'] = sym_type.xqss
            typ_param_dict['xds'] = sym_type.xds
            typ_param_dict['xd'] = sym_type.xd
            typ_param_dict['xq'] = sym_type.xq
            typ_param_dict['xl'] = sym_type.xl
            
            # Time constant parameters
            typ_param_dict['tdss'] = sym_type.tdss
            typ_param_dict['tqss'] = sym_type.tqss
            typ_param_dict['tds'] = sym_type.tds
            
            # Conditional parameters for turbo type 1 (steam)
            if sym_type.iturbo == 1:
                typ_param_dict['xqs'] = sym_type.xqs
                typ_param_dict['tqs'] = sym_type.tqs
            
            # Other parameters
            typ_param_dict['x0sy'] = sym_type.x0sy
            typ_param_dict['r0sy'] = sym_type.r0sy
            typ_param_dict['x2sy'] = sym_type.x2sy
            typ_param_dict['r2sy'] = sym_type.r2sy
            typ_param_dict['tag'] = sym_type.tag
            typ_param_dict['isat'] = sym_type.isat
            typ_param_dict['sg10'] = sym_type.sg10
            typ_param_dict['sg12'] = sym_type.sg12
            typ_param_dict['rstr'] = sym_type.rstr
            typ_param_dict['q_max'] = sym_type.q_max
            typ_param_dict['q_min'] = sym_type.q_min
            
            # Add type name for reference
            typ_param_dict['sym_type_name'] = sym_type.loc_name
            
            grid_graph.nodes[node_name][sym_type_key] = typ_param_dict

    # Add shunts as node parameters
    for i, shnt in enumerate(main_grid.GetContents('*.ElmShnt', 1)):
        node_name = shnt.bus1.cterm.loc_name
        key = shnt.loc_name

        param_dict = {
            'un': shnt.ushnm,
            'q_rated': shnt.qcapn,
        }
        grid_graph.nodes[node_name][f'{key}_param_dict'] = param_dict

    # Add External Grid parameters
    for i, ext_grid in enumerate(main_grid.GetContents('*.ElmXnet', 1)):
        node_name = ext_grid.bus1.cterm.loc_name
        key = ext_grid.loc_name

        param_dict = {
            'bustp': ext_grid.bustp,
            'snss': ext_grid.snss,
            'rntxn': ext_grid.rntxn,
            'x0tx1': ext_grid.x0tx1,
            'r0tx0': ext_grid.r0tx0,
        }
        grid_graph.nodes[node_name][f'{key}_param_dict'] = param_dict

    # Add IBR parameters
    for i, ibr in enumerate(main_grid.GetContents('*.ElmVac', 1)):
        if 'IBR' in ibr.loc_name:
            node_name = ibr.bus1.cterm.loc_name
            key = ibr.loc_name

            param_dict = {
                'Unom': ibr.Unom,
                'nphase': ibr.nphase,
                'usetp': ibr.usetp,
            }
            grid_graph.nodes[node_name][f'{key}_param_dict'] = param_dict

    # Add IBR Transformer parameters (ElmSind)
    for i, ibr_trafo in enumerate(main_grid.GetContents('*.ElmSind', 1)):
        if 'IBR' in ibr_trafo.loc_name:
            node1 = ibr_trafo.bus1.cterm.loc_name
            node2 = ibr_trafo.bus2.cterm.loc_name
            key = ibr_trafo.loc_name

            grid_graph.add_edge(node1, node2, key=key)

            param_dict = {
                'bus_1': node1,
                'bus_2': node2,
                'xrea': ibr_trafo.xrea,
                'rrea': ibr_trafo.rrea,
                'R0toR1': ibr_trafo.R0toR1,
                'X0toX1': ibr_trafo.X0toX1,
                'ucn': ibr_trafo.ucn,
                'Sn': ibr_trafo.Sn,
            }
            grid_graph.edges[(node1, node2, key)][f'{key}_param_dict'] = param_dict

    # Add IBR Control parameters (ElmMdl - FMU Controller) - associate with IBR bus
    for i, fmu_ctrl in enumerate(main_grid.GetContents('*.ElmMdl', 1)):
        if 'IBR' in fmu_ctrl.loc_name or 'FMUIBR' in fmu_ctrl.loc_name:
            # Find the associated IBR
            ibr_name = fmu_ctrl.loc_name.split('_cntrl')[0] if '_cntrl' in fmu_ctrl.loc_name else fmu_ctrl.loc_name.split('_')[0]
            ibr = main_grid.GetContents(f'{ibr_name}.ElmVac', 1)[0]
            if ibr:
                node_name = ibr.bus1.cterm.loc_name
                param_dict = {
                    'Deadband_lower_IqV': fmu_ctrl.GetAttribute('Deadband_lower_IqV'),
                    'Deadband_lower_IrU': fmu_ctrl.GetAttribute('Deadband_lower_IrU'),
                    'Deadband_lower_Pf': fmu_ctrl.GetAttribute('Deadband_lower_Pf'),
                    'Deadband_lower_QV': fmu_ctrl.GetAttribute('Deadband_lower_QV'),
                    'Deadband_upper_IqV': fmu_ctrl.GetAttribute('Deadband_upper_IqV'),
                    'Deadband_upper_IrU': fmu_ctrl.GetAttribute('Deadband_upper_IrU'),
                    'Deadband_upper_Pf': fmu_ctrl.GetAttribute('Deadband_upper_Pf'),
                    'Deadband_upper_QV': fmu_ctrl.GetAttribute('Deadband_upper_QV'),
                    'I_base': fmu_ctrl.GetAttribute('I_base'),
                    'Imax': fmu_ctrl.GetAttribute('Imax'),
                    'IqV_FLAG': fmu_ctrl.GetAttribute('IqV_FLAG'),
                    'IrV_FLAG': fmu_ctrl.GetAttribute('IrV_FLAG'),
                    'Ki_CC_NS': fmu_ctrl.GetAttribute('Ki_CC_NS'),
                    'Ki_CC_PS': fmu_ctrl.GetAttribute('Ki_CC_PS'),
                    'Ki_P': fmu_ctrl.GetAttribute('Ki_P'),
                    'Ki_PLL': fmu_ctrl.GetAttribute('Ki_PLL'),
                    'Ki_Q': fmu_ctrl.GetAttribute('Ki_Q'),
                    'Kp_CC_NS': fmu_ctrl.GetAttribute('Kp_CC_NS'),
                    'Kp_CC_PS': fmu_ctrl.GetAttribute('Kp_CC_PS'),
                    'Kp_IqV': fmu_ctrl.GetAttribute('Kp_IqV'),
                    'Kp_IrU': fmu_ctrl.GetAttribute('Kp_IrU'),
                    'Kp_P': fmu_ctrl.GetAttribute('Kp_P'),
                    'Kp_PLL': fmu_ctrl.GetAttribute('Kp_PLL'),
                    'Kp_Q': fmu_ctrl.GetAttribute('Kp_Q'),
                    'Kp_QV': fmu_ctrl.GetAttribute('Kp_QV'),
                    'LPF_DDSRF': fmu_ctrl.GetAttribute('LPF_DDSRF'),
                    'L_conv': fmu_ctrl.GetAttribute('L_conv'),
                    'P_FLAG': fmu_ctrl.GetAttribute('P_FLAG'),
                    'Pf_FLAG': fmu_ctrl.GetAttribute('Pf_FLAG'),
                    'Pf_lower_gain': fmu_ctrl.GetAttribute('Pf_lower_gain'),
                    'Pf_lower_limit': fmu_ctrl.GetAttribute('Pf_lower_limit'),
                    'Pf_upper_gain': fmu_ctrl.GetAttribute('Pf_upper_gain'),
                    'Pf_upper_limit': fmu_ctrl.GetAttribute('Pf_upper_limit'),
                    'Pmax': fmu_ctrl.GetAttribute('Pmax'),
                    'Pmin': fmu_ctrl.GetAttribute('Pmin'),
                    'QV_FLAG': fmu_ctrl.GetAttribute('QV_FLAG'),
                    'Q_FLAG': fmu_ctrl.GetAttribute('Q_FLAG'),
                    'Qmax': fmu_ctrl.GetAttribute('Qmax'),
                    'Qmin': fmu_ctrl.GetAttribute('Qmin'),
                    'R_conv': fmu_ctrl.GetAttribute('R_conv'),
                    'Sn': fmu_ctrl.GetAttribute('Sn'),
                    'T_IqV': fmu_ctrl.GetAttribute('T_IqV'),
                    'T_IrV': fmu_ctrl.GetAttribute('T_IrV'),
                    'T_P': fmu_ctrl.GetAttribute('T_P'),
                    'T_Pf': fmu_ctrl.GetAttribute('T_Pf'),
                    'T_Pm': fmu_ctrl.GetAttribute('T_Pm'),
                    'T_Q': fmu_ctrl.GetAttribute('T_Q'),
                    'T_QV': fmu_ctrl.GetAttribute('T_QV'),
                    'T_Qm': fmu_ctrl.GetAttribute('T_Qm'),
                    'V_base': fmu_ctrl.GetAttribute('V_base'),
                    'Z_base': fmu_ctrl.GetAttribute('Z_base'),
                    'dV_activate_IqV': fmu_ctrl.GetAttribute('dV_activate_IqV'),
                    'fn': fmu_ctrl.GetAttribute('fn'),
                }
                grid_graph.nodes[node_name][f'{fmu_ctrl.loc_name}_param_dict'] = param_dict

    # Add IBR Voltage/Angle Controllers (ElmLdfctrl) - associate with IBR bus
    for i, ctrl in enumerate(main_grid.GetContents('*.ElmLdfctrl', 1)):
        if 'VoltageCtrl' in ctrl.loc_name or 'AngleCtrl' in ctrl.loc_name:
            # Find the associated IBR
            ibr_name = ctrl.loc_name.replace('VoltageCtrl', '').replace('AngleCtrl', '').replace('IBR', '')
            ibr = main_grid.GetContents(f'*IBR{ibr_name}*.ElmVac', 1)[0]
            if ibr:
                node_name = ibr.bus1.cterm.loc_name
                param_dict = {
                    'i_ctrl': ctrl.i_ctrl,
                }
                grid_graph.nodes[node_name][f'{ctrl.loc_name}_param_dict'] = param_dict

    # Add Exciter parameters (ElmDsl) - associate with generator bus
    for i, exciter in enumerate(main_grid.GetContents('*.ElmDsl', 1)):
        if ('avr' in exciter.loc_name.lower() or 'exciter' in exciter.loc_name.lower() or 
            'cntrl' in exciter.loc_name.lower()) and 'IBR' not in exciter.loc_name:
            # Find the associated generator
            # Pattern: G1_cntrl_avr_AC1A -> G1
            if '_cntrl_' in exciter.loc_name:
                gen_name = exciter.loc_name.split('_cntrl_')[0]
            elif '_avr_' in exciter.loc_name:
                gen_name = exciter.loc_name.split('_avr_')[0]
                # Remove any remaining control suffix
                if '_' in gen_name:
                    gen_name = gen_name.split('_')[0]
            else:
                gen_name = exciter.loc_name.split('_')[0]
            
            gens = main_grid.GetContents(f'{gen_name}.ElmSym', 1)
            if gens:
                gen = gens[0]
                node_name = gen.bus1.cterm.loc_name
                param_dict = {
                    'Tr': exciter.Tr,
                    'Tb': exciter.Tb,
                    'Tc': exciter.Tc,
                    'Ka': exciter.Ka,
                    'Ta': exciter.Ta,
                    'Kc': exciter.Kc,
                    'Kf': exciter.Kf,
                    'Tf': exciter.Tf,
                    'Te': exciter.Te,
                    'Ke': exciter.Ke,
                    'Kd': exciter.Kd,
                    'E1': exciter.E1,
                    'SE1': exciter.SE1,
                    'E2': exciter.E2,
                    'SE2': exciter.SE2,
                    'Vamin': exciter.Vamin,
                    'Vrmin': exciter.Vrmin,
                    'Vamax': exciter.Vamax,
                    'Vrmax': exciter.Vrmax,
                }
                grid_graph.nodes[node_name][f'{exciter.loc_name}_param_dict'] = param_dict

    # Add Grounding resistance parameters (StarpointPermRes) - store as graph-level
    for i, ground_res in enumerate(main_grid.GetContents('*.ElmVac', 1)):
        if 'Starpoint' in ground_res.loc_name or 'PermRes' in ground_res.loc_name:
            param_dict = {
                'R1': ground_res.R1,
                'Unom': ground_res.Unom,
                'nphase': ground_res.nphase,
            }
            grid_graph.graph[f'NeutralPoint_{ground_res.loc_name}_param_dict'] = param_dict

    # Add Petersen Coil parameters - store as graph-level
    for i, pet_coil in enumerate(main_grid.GetContents('*.ElmVac', 1)):
        if 'Petersen' in pet_coil.loc_name or 'coil' in pet_coil.loc_name.lower():
            param_dict = {
                'X1': pet_coil.X1,
                'Unom': pet_coil.Unom,
                'nphase': pet_coil.nphase,
                'outserv': pet_coil.outserv,
            }
            grid_graph.graph[f'NeutralPoint_{pet_coil.loc_name}_param_dict'] = param_dict

    # Add Motor parameters
    for i, motor in enumerate(main_grid.GetContents('*.ElmAsm', 1)):
        node_name = motor.bus1.cterm.loc_name
        key = motor.loc_name

        param_dict = {
            'motor_type': motor.typ_id.loc_name if motor.typ_id else None,
        }
        grid_graph.nodes[node_name][f'{key}_param_dict'] = param_dict

    # Add Neutral Point parameters (ElmNec) - store as graph-level with NeutralPoint prefix
    for i, nec in enumerate(main_grid.GetContents('*.ElmNec', 1)):
        param_dict = {
            'Unom': nec.Unom,
            'Curn': nec.Curn,
            'iintgnd': nec.iintgnd,
        }
        # Store with NeutralPoint prefix for proper categorization
        grid_graph.graph[f'NeutralPoint_{nec.loc_name}_param_dict'] = param_dict

    return grid_graph

if __name__ == "__main__":
    import powerfactory  # the Python folder of PowerFactory must be on PYTHONPATH

    pf = powerfactory.GetApplicationExt()
    pf.ClearOutputWindow()

    for grid_name in ["CigreMVGrid", "Template20kV", "Template110kV"]:

        pf.ActivateProject(grid_name)

        active_project = pf.GetActiveProject()
        main_grid = active_project.GetContents('*Main*.ElmNet', 1)[0]

        grid_graph = create_graph_from_existing_grid(main_grid)

        # Save the graph
        with open(f'graph_{grid_name}.pickle', 'wb') as f:
            pickle.dump(grid_graph, f)

        print(f"Graph created and saved!")
        print(f"Nodes: {grid_graph.number_of_nodes()}")
        print(f"Edges: {grid_graph.number_of_edges()}")





