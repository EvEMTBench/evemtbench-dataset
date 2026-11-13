import numpy as np

from util.pf_utils import get_pf_lib

np.random.seed(0)

import powerfactory
pf = powerfactory.GetApplicationExt()

user = pf.GetCurrentUser()
parent_lib = get_pf_lib(user, "CustomTypeLib")

symtype_lib = get_pf_lib(parent_lib, "SymTypes")

# Delete old cables
sym_types = parent_lib.GetContents("*.TypSym*", 1)
for sym_type in sym_types:
    sym_type.Delete()



# create 1000 realistic cable types
for i in range(1000):
    pf.SetWriteCacheEnabled(1)

    sym_type = symtype_lib.CreateObject("TypSym", f"SymType {i}")
    turbo_type = np.random.choice([0, 1])  # 0 for hydro (schenkelpol/salient pole), 1 for steam/gas (round-rotor, vollpol)
    sym_type.iturbo = int(turbo_type)

    if turbo_type == 0:
        # hydro (schenkelpol/salient pole)
        sym_type.sgn = np.random.uniform(17.5, 700)
        sym_type.cosn = np.random.uniform(0.8, 0.95)

        sym_type.xdss = np.random.uniform(0.12, 0.3)
        sym_type.xqss = np.random.uniform(1 * sym_type.xdss, 3 * sym_type.xdss)  # herold

        sym_type.xds = max(np.random.uniform(0.20, 0.45), sym_type.xdss * 1.01)

        sym_type.xd = max(np.random.uniform(0.8, 1.4), sym_type.xds * 1.01)
        sym_type.xq = max(np.random.uniform(0.6 * sym_type.xd, 0.7 * sym_type.xd), sym_type.xqss * 1.01)

        sym_type.tds = np.random.uniform(0.7, 2.2)

        sym_type.tdss = np.random.uniform(0.02, 0.1)
        sym_type.tqss = np.random.uniform(0.017, 0.035)

        sym_type.x0sy = np.random.uniform(0.05, 0.2)
        sym_type.r0sy = 0
        sym_type.x2sy = np.random.uniform(0.9, 1.1) * sym_type.xdss
        sym_type.r2sy = np.random.uniform(0.014, 0.060)  # anderson

        sym_type.tag = np.random.uniform(5, 10)

        sym_type.isat = 3
        sym_type.sg10 = np.random.uniform(0.064, 0.313)
        sym_type.sg12 = np.random.uniform(max(sym_type.sg10, 0.282), 1.018)

        sym_type.rstr = np.random.uniform(0.0014, 0.006)
        sym_type.xl = np.random.uniform(0.12, min(0.9, sym_type.xdss, sym_type.xqss))

    elif turbo_type == 1:
        # steam/gas (round-rotor, vollpol, turbomaschine)
        sym_type.sgn = np.random.uniform(25, 1200)
        sym_type.cosn = np.random.uniform(0.8, 0.975)

        sym_type.xdss = np.random.uniform(0.09, 0.22)
        sym_type.xqss = np.random.uniform(1, 1.1) * sym_type.xdss  # herold

        sym_type.xds = max(np.random.uniform(0.14, 0.35), sym_type.xdss * 1.01)
        sym_type.xqs = max(np.random.uniform(0.90 * sym_type.xds, 1.0 * sym_type.xds), sym_type.xqss * 1.01)

        sym_type.xd = max(np.random.uniform(1.4, 3.0), sym_type.xds * 1.01)
        sym_type.xq = max(np.random.uniform(0.9, 1.0) * sym_type.xd, sym_type.xqs * 1.01)

        sym_type.tds = np.random.uniform(0.8, 1.5)
        sym_type.tqs = np.random.uniform(0.298, 0.756)

        sym_type.tdss = np.random.uniform(0.02, 0.05)
        sym_type.tqss = np.random.uniform(0.01, 0.035)

        sym_type.x0sy = np.random.uniform(0.03, 0.1)
        sym_type.r0sy = 0
        sym_type.x2sy = np.random.uniform(0.9, 1.1) * sym_type.xdss
        sym_type.r2sy = np.random.uniform(0.005, 0.029)  # anderson

        sym_type.tag = np.random.uniform(5, 10)

        sym_type.isat = 3
        sym_type.sg10 = np.random.uniform(0.07, 0.340)
        sym_type.sg12 = np.random.uniform(max(sym_type.sg10, 0.290), 1.12)

        sym_type.rstr = np.random.uniform(0.0016, 0.005)
        sym_type.xl = np.random.uniform(0.07, min(0.333, sym_type.xdss, sym_type.xqss))
    else:
        raise NotImplementedError

    if sym_type.sgn <= 40:
        sym_type.ugn = 6.3
    elif sym_type.sgn <= 200:
        sym_type.ugn = 10.5
    elif sym_type.sgn <= 800:
        sym_type.ugn = 21
    else:
        sym_type.ugn = 27

    sym_type.q_max = 0.48  # corresponding to cosphi ~0.90
    sym_type.q_min = -0.41  # corresponding to cosphi ~0.925

    pf.WriteChangesToDb()
    pf.SetWriteCacheEnabled(0)


parent_lib = get_pf_lib(user, "CustomTypeLib")
symtype_lib = get_pf_lib(parent_lib, "SymTypes")
symtype_345_lib = get_pf_lib(symtype_lib, "345kV")
sym_type_110_lib = get_pf_lib(symtype_lib, "110kV")

for sym_type in symtype_lib.GetContents("*.TypSym"):
    if sym_type.sgn <= 40:
        sym_type_110_lib.Move(sym_type)
    elif sym_type.sgn <= 200:
        target_lib = np.random.choice([sym_type_110_lib, symtype_345_lib])
        target_lib.Move(sym_type)
    else:
        symtype_345_lib.Move(sym_type)


print("Sym Lib successfully completed.")


