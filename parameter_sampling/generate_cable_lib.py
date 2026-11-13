import sys
import numpy as np
import math
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
np.random.seed(0)

from util.pf_utils import get_pf_lib
import powerfactory
pf = powerfactory.GetApplicationExt()
# pf.Show()

user = pf.GetCurrentUser()
input_options = user.GetContents("*Settings Single Core Cable Type.OptTypcab", 1)[0]
assert input_options.iopt_R == "dcr"

parent_lib = get_pf_lib(user, "CustomTypeLib")

cable_type_lib = get_pf_lib(parent_lib, "CableTypes")
cable_type_lib_20kV = get_pf_lib(cable_type_lib, "20kV")
cable_lib = get_pf_lib(parent_lib, "Cables")
cable_lib_20kV = get_pf_lib(cable_lib, "20kV")

# Delete old cables
cable_types = parent_lib.GetContents("*.TypCab", 1)
for cable in cable_types:
    cable.Delete()

cables = parent_lib.GetContents("*.TypCabsys", 1)
for cable in cables:
    cable.Delete()

insulation_materials = ['PE', 'XLPE', 'EPR']
conductor_areas = [50, 70, 95, 120, 150, 185, 240, 300, 400, 500]
sheath_areas = [16, 16, 16,  16,  25,  25,  25,  25,  25,  25]
r_dc_conductor = [0.641,
        0.443,
        0.320,
        0.253,
        0.206,
        0.164,
        0.125,
        0.100,
        0.0778,
        0.0605,
        ]

tand = {
    "PE": 0.3*1e-3,
    "XLPE": 0.4*1e-3,
    "EPR": 5*1e-3,
}

epsr = {
    "PE": 2.3,
    "XLPE": 2.4,
    "EPR": 3,
}

for insulation in insulation_materials:
    for i, area in enumerate(conductor_areas):
        if insulation == 'PE':
            i_short = '2Y'
        elif insulation == 'XLPE':
            i_short = '2X'
        elif insulation == 'EPR':
            i_short = '3G'
        else:
            raise NotImplementedError("Unknown insulation material")
        # N = Norm, A = Aluminum Conductor, S = Copper Shield, 2Y = PE Oversheath
        name = f"NA{i_short}S2Y 1x{area}RM"
        cable_type = cable_type_lib_20kV.CreateObject("TypCab", f"{name}")

        # Conductor and Sheath exist, Armour and Serving do not exist.
        cable_type.cHasEl = [1, 1, 0]
        cable_type.cHasIns = [1, 1, 0]
        cable_type.uline = 20 # kV
        cable_type.typCon = 'cmp'

        # calc thickness in mm
        thickness_conductor = math.sqrt(area / math.pi)  # in millimeters
        thickness_insulation = 5.5
        thickness_sheath = math.sqrt((sheath_areas[i] / 3.14159) + (thickness_conductor + thickness_insulation) ** 2) - (thickness_conductor + thickness_insulation)
        thickness_oversheath = 2.5

        # thickness of layers (conducting)
        cable_type.cThEl = [thickness_conductor, thickness_sheath, 1.0]
        # resistivity of aluminum and copper.
        cable_type.crho = [2.8264, 1.7241, 1.0]
        cable_type.alpha = [0.00403, 0.00393, 0.00393]
        cable_type_dc_resistances = cable_type.rpha
        cable_type_dc_resistances[0] = r_dc_conductor[i]
        cable_type.rpha = cable_type_dc_resistances

        # thickness of layers (insulation)
        cable_type.thIns = [thickness_insulation, thickness_oversheath, 1.0]
        # Dielectric loss
        cable_type.ctand = [tand[insulation], tand["PE"], 1]
        # Relative permittivity
        cable_type.cepsr = [epsr[insulation], epsr["PE"], 1]


# create 1000 realistic cable types
for i in range(1000):
    pf.SetWriteCacheEnabled(1)

    cable_types = cable_type_lib_20kV.GetContents("*.TypCab")
    cable = cable_lib_20kV.CreateObject("TypCabsys", f"Cable{i}")

    cable_type = np.random.choice(cable_types)
    cable.circPosInput = 0
    cable.pcab_c = [cable_type]

    bury_depth = np.random.uniform(0.7, 1.2)
    # 0 for flat, 1 for trifold
    format = np.random.choice(['flat', 'trifold'])

    if format == 'flat':
        phsdist = np.random.uniform(cable_type.diaCab/1000 + 0.07, 0.3)
        x1 = -phsdist
        x2 = 0
        x3 = phsdist
        y1 = bury_depth
        y2 = bury_depth
        y3 = bury_depth
        cable.xy_c = [[x1, x2, x3, y1, y2, y3]]
    elif format == 'trifold':
        # for triangular order the cables are very close together.
        phsdist = cable_type.diaCab/1000 + 0.005
        # Equilateral triangle with side length phsdist
        height = phsdist * math.sqrt(3) / 2
        x1 = -phsdist / 2
        x2 = 0
        x3 = phsdist / 2
        y1 = bury_depth + height
        y2 = bury_depth
        y3 = bury_depth + height
        cable.xy_c = [[x1, x2, x3, y1, y2, y3]]

    else:
        raise NotImplementedError("cFormat must be 0 or 1")

    cable.rhoEarth = np.random.uniform(5, 500)

    pf.WriteChangesToDb()
    pf.SetWriteCacheEnabled(0)


print("Cable Lib successfully completed.")
