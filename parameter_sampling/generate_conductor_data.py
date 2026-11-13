import numpy as np
from util.pf_utils import get_pf_lib

np.random.seed(0)

import powerfactory
pf = powerfactory.GetApplicationExt()
# pf.Show()


user = pf.GetCurrentUser()
parent_lib = get_pf_lib(user, "CustomTypeLib")

conductor_lib = get_pf_lib(parent_lib, "Conductors")


# Delete old cables
conductors = parent_lib.GetContents("*.TypCon", 1)
for conductor in conductors:
    conductor.Delete()

def gmr(r, q):
    term1 = (3 * q**2 - r**2) / (4 * (r**2 - q**2))
    term2 = (q**4) / ((r**2 - q**2)**2) * np.log(r / q)
    return r * np.exp(term1 - term2)


# ast conductors are used for almost all HV lines
ast_conductors = [
    {"Name": "15-AL1/3-ST1A", "NominalCrossSection": 16, "InnerDiameter": 1.80, "OuterDiameter": 5.40, "DCResistance": 1.8769, "RatedCurrent": 105},
    {"Name": "24-AL1/4-ST1A", "NominalCrossSection": 25, "InnerDiameter": 2.25, "OuterDiameter": 6.75, "DCResistance": 1.2012, "RatedCurrent": 140},
    {"Name": "34-AL1/6-ST1A", "NominalCrossSection": 35, "InnerDiameter": 2.70, "OuterDiameter": 8.10, "DCResistance": 0.8342, "RatedCurrent": 170},
    {"Name": "48-AL1/8-ST1A", "NominalCrossSection": 50, "InnerDiameter": 3.20, "OuterDiameter": 9.60, "DCResistance": 0.5939, "RatedCurrent": 210},
    {"Name": "70-AL1/11-ST1A", "NominalCrossSection": 70, "InnerDiameter": 4.32, "OuterDiameter": 11.70, "DCResistance": 0.4132, "RatedCurrent": 290},
    {"Name": "94-AL1/15-ST1A", "NominalCrossSection": 95, "InnerDiameter": 5.01, "OuterDiameter": 13.60, "DCResistance": 0.3060, "RatedCurrent": 350},
    {"Name": "122-AL1/20-ST1A", "NominalCrossSection": 120, "InnerDiameter": 5.70, "OuterDiameter": 15.50, "DCResistance": 0.2376, "RatedCurrent": 410},
    {"Name": "128-AL1/30-ST1A", "NominalCrossSection": 125, "InnerDiameter": 6.99, "OuterDiameter": 16.30, "DCResistance": 0.2260, "RatedCurrent": 425},
    {"Name": "149-AL1/24-ST1A", "NominalCrossSection": 150, "InnerDiameter": 6.30, "OuterDiameter": 17.10, "DCResistance": 0.1940, "RatedCurrent": 470},
    {"Name": "172-AL1/40-ST1A", "NominalCrossSection": 170, "InnerDiameter": 8.10, "OuterDiameter": 18.90, "DCResistance": 0.1683, "RatedCurrent": 520},
    {"Name": "184-AL1/30-ST1A", "NominalCrossSection": 185, "InnerDiameter": 6.99, "OuterDiameter": 19.00, "DCResistance": 0.1571, "RatedCurrent": 535},
    {"Name": "209-AL1/34-ST1A", "NominalCrossSection": 210, "InnerDiameter": 7.47, "OuterDiameter": 20.30, "DCResistance": 0.1381, "RatedCurrent": 590},
    {"Name": "212-AL1/49-ST1A", "NominalCrossSection": 210, "InnerDiameter": 9.00, "OuterDiameter": 21.00, "DCResistance": 0.1363, "RatedCurrent": 610},
    {"Name": "231-AL1/30-ST1A", "NominalCrossSection": 230, "InnerDiameter": 6.99, "OuterDiameter": 21.00, "DCResistance": 0.1250, "RatedCurrent": 630},
    {"Name": "243-AL1/39-ST1A", "NominalCrossSection": 240, "InnerDiameter": 8.04, "OuterDiameter": 21.80, "DCResistance": 0.1188, "RatedCurrent": 645},
    {"Name": "264-AL1/34-ST1A", "NominalCrossSection": 265, "InnerDiameter": 7.47, "OuterDiameter": 22.40, "DCResistance": 0.1095, "RatedCurrent": 680},
    {"Name": "304-AL1/49-ST1A", "NominalCrossSection": 300, "InnerDiameter": 9.00, "OuterDiameter": 24.40, "DCResistance": 0.0949, "RatedCurrent": 740},
    {"Name": "305-AL1/39-ST1A", "NominalCrossSection": 305, "InnerDiameter": 8.04, "OuterDiameter": 24.10, "DCResistance": 0.0949, "RatedCurrent": 740},
    {"Name": "339-AL1/30-ST1A", "NominalCrossSection": 340, "InnerDiameter": 6.99, "OuterDiameter": 25.00, "DCResistance": 0.0852, "RatedCurrent": 790},
    {"Name": "382-AL1/49-ST1A", "NominalCrossSection": 380, "InnerDiameter": 9.00, "OuterDiameter": 27.00, "DCResistance": 0.0758, "RatedCurrent": 840},
    {"Name": "386-AL1/34-ST1A", "NominalCrossSection": 385, "InnerDiameter": 7.47, "OuterDiameter": 26.70, "DCResistance": 0.0749, "RatedCurrent": 850},
    {"Name": "434-AL1/56-ST1A", "NominalCrossSection": 435, "InnerDiameter": 9.60, "OuterDiameter": 28.80, "DCResistance": 0.0666, "RatedCurrent": 900},
    {"Name": "449-AL1/39-ST1A", "NominalCrossSection": 450, "InnerDiameter": 8.04, "OuterDiameter": 28.70, "DCResistance": 0.0644, "RatedCurrent": 920},
    {"Name": "490-AL1/64-ST1A", "NominalCrossSection": 490, "InnerDiameter": 10.20, "OuterDiameter": 30.60, "DCResistance": 0.0590, "RatedCurrent": 960},
    {"Name": "494-AL1/34-ST1A", "NominalCrossSection": 495, "InnerDiameter": 7.47, "OuterDiameter": 29.90, "DCResistance": 0.0584, "RatedCurrent": 985},
    {"Name": "511-AL1/45-ST1A", "NominalCrossSection": 510, "InnerDiameter": 8.61, "OuterDiameter": 30.70, "DCResistance": 0.0566, "RatedCurrent": 995},
    {"Name": "550-AL1/71-ST1A", "NominalCrossSection": 550, "InnerDiameter": 10.80, "OuterDiameter": 32.40, "DCResistance": 0.0526, "RatedCurrent": 1020},
    {"Name": "562-AL1/49-ST1A", "NominalCrossSection": 560, "InnerDiameter": 9.00, "OuterDiameter": 32.20, "DCResistance": 0.0515, "RatedCurrent": 1040},
    {"Name": "571-AL1/39-ST1A", "NominalCrossSection": 570, "InnerDiameter": 8.04, "OuterDiameter": 32.20, "DCResistance": 0.0506, "RatedCurrent": 1050},
    {"Name": "653-AL1/45-ST1A", "NominalCrossSection": 650, "InnerDiameter": 8.61, "OuterDiameter": 34.40, "DCResistance": 0.0442, "RatedCurrent": 1120},
    {"Name": "679-AL1/86-ST1A", "NominalCrossSection": 680, "InnerDiameter": 12.00, "OuterDiameter": 36.00, "DCResistance": 0.0426, "RatedCurrent": 1150},
    {"Name": "1046-AL1/45-ST1A", "NominalCrossSection": 1045, "InnerDiameter": 8.61, "OuterDiameter": 43.00, "DCResistance": 0.0277, "RatedCurrent": 1580}
]


al_conductors = [
    {"Name": "16-AL1", "NominalCrossSection": 15.9, "OuterDiameter": 5.10, "DCResistance": 1.7986, "RatedCurrent": 110},
    {"Name": "24-AL1", "NominalCrossSection": 24.2, "OuterDiameter": 6.30, "DCResistance": 1.181, "RatedCurrent": 145},
    {"Name": "34-AL1", "NominalCrossSection": 34.4, "OuterDiameter": 7.50, "DCResistance": 0.833, "RatedCurrent": 180},
    {"Name": "49-AL1", "NominalCrossSection": 49.5, "OuterDiameter": 9.00, "DCResistance": 0.579, "RatedCurrent": 225},
    {"Name": "48-AL1", "NominalCrossSection": 48.3, "OuterDiameter": 9.00, "DCResistance": 0.595, "RatedCurrent": 225},
    {"Name": "66-AL1", "NominalCrossSection": 65.8, "OuterDiameter": 10.50, "DCResistance": 0.437, "RatedCurrent": 270},
    {"Name": "93-AL1", "NominalCrossSection": 93.3, "OuterDiameter": 12.50, "DCResistance": 0.308, "RatedCurrent": 340},
    {"Name": "117-AL1", "NominalCrossSection": 117.0, "OuterDiameter": 12.50, "DCResistance": 0.246, "RatedCurrent": 390},
    {"Name": "147-AL1", "NominalCrossSection": 147.1, "OuterDiameter": 15.75, "DCResistance": 0.196, "RatedCurrent": 455},
    {"Name": "182-AL1", "NominalCrossSection": 181.6, "OuterDiameter": 17.50, "DCResistance": 0.159, "RatedCurrent": 520},
    {"Name": "243-AL1", "NominalCrossSection": 242.5, "OuterDiameter": 20.30, "DCResistance": 0.119, "RatedCurrent": 625},
    {"Name": "299-AL1", "NominalCrossSection": 299.4, "OuterDiameter": 22.50, "DCResistance": 0.097, "RatedCurrent": 710},
    {"Name": "400-AL1", "NominalCrossSection": 400.1, "OuterDiameter": 26.00, "DCResistance": 0.072, "RatedCurrent": 855},
    {"Name": "450-AL1", "NominalCrossSection": 449.8, "OuterDiameter": 27.60, "DCResistance": 0.065, "RatedCurrent": 910},
    {"Name": "500-AL1", "NominalCrossSection": 499.8, "OuterDiameter": 29.10, "DCResistance": 0.058, "RatedCurrent": 990},
    {"Name": "626-AL1", "NominalCrossSection": 626.2, "OuterDiameter": 32.60, "DCResistance": 0.046, "RatedCurrent": 1140},
    {"Name": "802-AL1", "NominalCrossSection": 802.1, "OuterDiameter": 36.90, "DCResistance": 0.036, "RatedCurrent": 1340},
    {"Name": "1000-AL1", "NominalCrossSection": 999.7, "OuterDiameter": 41.10, "DCResistance": 0.029, "RatedCurrent": 1540}
]

aldrey_conductors = [
    {"Name": "16-ALD", "NominalCrossSection": 15.89, "OuterDiameter": 5.1, "DCResistance": 2.0910, "RatedCurrent": 105},
    {"Name": "25-ALD", "NominalCrossSection": 24.25, "OuterDiameter": 6.3, "DCResistance": 1.3702, "RatedCurrent": 135},
    {"Name": "35-ALD", "NominalCrossSection": 34.36, "OuterDiameter": 7.5, "DCResistance": 0.9669, "RatedCurrent": 170},
    {"Name": "50-ALD", "NominalCrossSection": 48.35, "OuterDiameter": 9.0, "DCResistance": 0.6905, "RatedCurrent": 210},
    {"Name": "70-ALD", "NominalCrossSection": 65.81, "OuterDiameter": 10.5, "DCResistance": 0.5073, "RatedCurrent": 255},
    {"Name": "95-ALD", "NominalCrossSection": 93.27, "OuterDiameter": 12.5, "DCResistance": 0.3580, "RatedCurrent": 320},
    {"Name": "120-ALD", "NominalCrossSection": 116.99, "OuterDiameter": 14.0, "DCResistance": 0.2854, "RatedCurrent": 365},
    {"Name": "150-ALD", "NominalCrossSection": 147.11, "OuterDiameter": 15.8, "DCResistance": 0.2274, "RatedCurrent": 425},
    {"Name": "185-ALD", "NominalCrossSection": 181.62, "OuterDiameter": 17.5, "DCResistance": 0.1842, "RatedCurrent": 490},
    {"Name": "240-ALD", "NominalCrossSection": 242.54, "OuterDiameter": 20.3, "DCResistance": 0.1383, "RatedCurrent": 585},
    {"Name": "300-ALD", "NominalCrossSection": 299.43, "OuterDiameter": 22.5, "DCResistance": 0.1120, "RatedCurrent": 670},
    {"Name": "400-ALD", "NominalCrossSection": 400.14, "OuterDiameter": 26.0, "DCResistance": 0.0838, "RatedCurrent": 810},
    {"Name": "500-ALD", "NominalCrossSection": 499.83, "OuterDiameter": 29.1, "DCResistance": 0.0671, "RatedCurrent": 930},
    {"Name": "625-ALD", "NominalCrossSection": 626.20, "OuterDiameter": 32.6, "DCResistance": 0.0537, "RatedCurrent": 1075},
    {"Name": "800-ALD", "NominalCrossSection": 802.09, "OuterDiameter": 36.9, "DCResistance": 0.0419, "RatedCurrent": 1255},
    {"Name": "1000-ALD", "NominalCrossSection": 999.71, "OuterDiameter": 41.1, "DCResistance": 0.0336, "RatedCurrent": 1450}
]




for voltage in [20, 110, 345]:
    for n_bundle in [1, 2, 3, 4]:
        if voltage == 20:
            if not n_bundle == 1:
                continue
        elif voltage == 110:
            if n_bundle > 2:
                continue
        elif voltage == 345:
            if n_bundle < 3:
                continue

        conductor_lib_vn = get_pf_lib(conductor_lib, f"{voltage}kV")

        if voltage == 20:
            # Create conductors
            for row in al_conductors:
                if not 100 <= row["RatedCurrent"] <= 650:
                    continue
                pf.SetWriteCacheEnabled(1)
                conductor = conductor_lib_vn.CreateObject("TypCon", row["Name"])
                conductor.ncsub = n_bundle
                conductor.uline = voltage
                conductor.sline = row["RatedCurrent"]/1000
                conductor.iModel = 0  # Solid Conductor
                conductor.rpha = row["DCResistance"]
                conductor.diaco = row["OuterDiameter"]
                conductor.erpha = (conductor.diaco / 2) * np.exp(-1/4)
                conductor.iopt_inp = "mat"
                pf.WriteChangesToDb()
                conductor.mlei = 'Al'
                pf.WriteChangesToDb()
                pf.SetWriteCacheEnabled(0)

            for row in aldrey_conductors:
                if not 100 <= row["RatedCurrent"] <= 650:
                    continue
                pf.SetWriteCacheEnabled(1)
                conductor = conductor_lib_vn.CreateObject("TypCon", row["Name"])
                conductor.ncsub = n_bundle
                conductor.uline = voltage
                conductor.sline = row["RatedCurrent"]/1000
                conductor.iModel = 0  # Solid Conductor
                conductor.rpha = row["DCResistance"]
                conductor.diaco = row["OuterDiameter"]
                conductor.erpha = (conductor.diaco / 2) * np.exp(-1/4)
                conductor.iopt_inp = "mat"
                pf.WriteChangesToDb()
                conductor.mlei = 'Ad'
                pf.WriteChangesToDb()
                pf.SetWriteCacheEnabled(0)

        # Create conductors
        for row in ast_conductors:
            pf.SetWriteCacheEnabled(1)

            if voltage == 20:
                if not 100 <= row["RatedCurrent"] <= 650:
                    continue
                conductor = conductor_lib_vn.CreateObject("TypCon", row["Name"])
                conductor.ncsub = n_bundle
            elif voltage == 110:
                if not 185 <= row["NominalCrossSection"] <= 525:
                    continue

                conductor = conductor_lib_vn.CreateObject("TypCon", row["Name"] + f" x{n_bundle}")
                conductor.ncsub = n_bundle
                bundle_spacing = np.random.uniform(0.4, 0.5)  # in meter
                conductor.dsubc = bundle_spacing

            elif voltage == 345:
                if not 185 <= row["NominalCrossSection"] <= 800:
                    continue
                conductor = conductor_lib_vn.CreateObject("TypCon", row["Name"] + f" x{n_bundle}")
                conductor.ncsub = n_bundle
                bundle_spacing = np.random.uniform(0.4, 0.5)  # in meter
                conductor.dsubc = bundle_spacing
            else:
                raise NotImplementedError

            conductor.uline = voltage
            conductor.sline = row["RatedCurrent"]/1000
            conductor.iModel = 1  # Hohlleiter / Tube Conductor
            conductor.rpha = row["DCResistance"]
            conductor.diaco = row["OuterDiameter"]
            conductor.diatub = row["InnerDiameter"]
            conductor.erpha = gmr(row["OuterDiameter"] / 2, row["InnerDiameter"] / 2)
            conductor.iopt_inp = "mat"
            pf.WriteChangesToDb()
            conductor.mlei = 'As'
            pf.WriteChangesToDb()
            pf.SetWriteCacheEnabled(0)



conductor_lib_earth = get_pf_lib(conductor_lib, "Earthwires")
for voltage in [110, 345]:
    conductor_lib_earth_vn = get_pf_lib(conductor_lib_earth, f"{voltage}kV")
    for row in ast_conductors:
        if not 35 <= row["NominalCrossSection"] <= 95:
            continue
        pf.SetWriteCacheEnabled(1)
        conductor = conductor_lib_earth_vn.CreateObject("TypCon", row["Name"])
        conductor.ncsub = 1
        conductor.uline = voltage
        conductor.sline = row["RatedCurrent"] / 1000
        conductor.iModel = 0  # Solid Conductor
        conductor.rpha = row["DCResistance"]
        conductor.diaco = row["OuterDiameter"]
        conductor.erpha = (conductor.diaco / 2) * np.exp(-1 / 4)
        conductor.iopt_inp = "mat"
        pf.WriteChangesToDb()
        conductor.mlei = 'As'
        pf.WriteChangesToDb()
        pf.SetWriteCacheEnabled(0)


print("Conductor Lib successfully completed.")
