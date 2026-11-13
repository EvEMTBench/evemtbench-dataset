import math
import os
import sys
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
np.random.seed(0)

from util.pf_utils import get_pf_lib
import powerfactory
pf = powerfactory.GetApplicationExt()
# pf.Show()

def poly_to_rms_table(
    psi0,
    xmlin,
    xmair,
    ksat,
    fnom,
    v_min,
    v_max,
    n_points,
):

    # ------------------------------------------------------------------
    # Intermediate parameters (Technical Reference, Section 6.2.1)
    # ------------------------------------------------------------------
    omega0 = 2.0 * np.pi * fnom          # ω₀ [rad/s]

    bm    = omega0 / xmlin                # unsaturated  [rad/s / p.u.]
    bmsat = omega0 / xmair               # saturated     [rad/s / p.u.]

    Psi_Mknee = (ksat + 1) / ksat * psi0  # [p.u.]

    ratio = (bmsat / bm - 1.0) / (ksat + 1.0)
    Psi0_int = Psi_Mknee * np.exp(-np.log(ratio) / ksat)  # [p.u.]

    # Knee-point current (eq. 135)
    i_knee = (bm / omega0) * Psi_Mknee * (
        1.0 + (Psi_Mknee / Psi0_int) ** ksat
    )

    def iMX_func(Psi: np.ndarray) -> np.ndarray:
        return np.where(
            Psi > Psi_Mknee,
            i_knee + (bmsat / omega0) * (Psi - Psi_Mknee),
            np.where(
                Psi < -Psi_Mknee,
                -i_knee + (bmsat / omega0) * (Psi + Psi_Mknee),
                (bm / omega0) * Psi * (1.0 + np.abs(Psi / Psi0_int) ** ksat),
            ),
        )

    i = []
    u = []

    for v_rms in np.linspace(v_min, v_max, n_points):
        Psi_peak = v_rms
        iMX_t = iMX_func(Psi_peak)
        u.append(float(v_rms))
        i.append(float(iMX_t))

    # also add linear part
    i = [0.0, (bm / omega0) * 1.11] + i
    u = [0.0, 1.11] + u

    return i, u



def generate_20_04kV_trafo_lib(parent_lib, fn):
    grid_trafo_lib = get_pf_lib(parent_lib, "GridTrafos")
    grid_trafo_lib_20kV = get_pf_lib(grid_trafo_lib, "20/0_4kV")

    trafo_params = [
        {
            "sn": 160,
            "u_k": {"min": 0.04, "max": 0.04},
            "P_k": {"min": 2.35, "max": 3.10},
            "P_l": {"min": 0.375, "max": 0.460},
            "I_l": {"min": 0.011, "max": 0.017}
        },
        {
            "sn": 250,
            "u_k": {"min": 0.04, "max": 0.06},
            "P_k": {"min": 2.75, "max": 4.2},
            "P_l": {"min": 0.425, "max": 0.65},
            "I_l": {"min": 0.011, "max": 0.017}
        },
        {
            "sn": 400,
            "u_k": {"min": 0.04, "max": 0.06},
            "P_k": {"min": 3.85, "max": 6.0},
            "P_l": {"min": 0.61, "max": 0.93},
            "I_l": {"min": 0.009, "max": 0.014}
        },
        {
            "sn": 630,
            "u_k": {"min": 0.04, "max": 0.06},
            "P_k": {"min": 5.4, "max": 8.7},
            "P_l": {"min": 0.80, "max": 1.3},
            "I_l": {"min": 0.008, "max": 0.012}
        },
        {
            "sn": 1000,
            "u_k": {"min": 0.06, "max": 0.06},
            "P_k": {"min": 9.5, "max": 13.0},
            "P_l": {"min": 1.1, "max": 1.7},
            "I_l": {"min": 0.008, "max": 0.012}
        },
        {
            "sn": 1600,
            "u_k": {"min": 0.06, "max": 0.06},
            "P_k": {"min": 14.0, "max": 20.0},
            "P_l": {"min": 1.7, "max": 2.6},
            "I_l": {"min": 0.007, "max": 0.011}
        },
    ]

    for i in range(1000):
        trafo_param_set = np.random.choice(trafo_params)
        sn = trafo_param_set["sn"] / 1000
        trafo = grid_trafo_lib_20kV.CreateObject("TypTr2", f"{sn} MVA 20/0.4 {fn} Hz Trafo{i}")

        trafo.strn = sn
        trafo.frnom = fn
        trafo.utrn_h = 20
        trafo.utrn_l = 0.4

        if sn <= 250 / 1000:
            vector_group = np.random.choice(["Dyn", "Yzn"])
        else:
            vector_group = "Dyn"

        if vector_group == "Dyn":
            trafo.tr2cn_h = "D"
            trafo.tr2cn_l = "YN"
            trafo.nt2ag = 5
        elif vector_group == "Yzn":
            trafo.tr2cn_h = "Y"
            trafo.tr2cn_l = "ZN"
            trafo.nt2ag = 5
        else:
            raise NotImplementedError("Vector class not supported")

        trafo.uktr = np.random.uniform(trafo_param_set["u_k"]["min"], trafo_param_set["u_k"]["max"]) * 100
        trafo.pcutr = np.random.uniform(trafo_param_set["P_k"]["min"], trafo_param_set["P_k"]["max"])
        trafo.curmg = np.random.uniform(trafo_param_set["I_l"]["min"], trafo_param_set["I_l"]["max"]) * 100
        trafo.pfe = np.random.uniform(trafo_param_set["P_l"]["min"], trafo_param_set["P_l"]["max"])

        if vector_group == "Dyn":
            trafo.x0pu = np.random.uniform(0.95, 1.0) * trafo.x1pu
            trafo.r0pu = np.random.uniform(1.2, 1.8) * trafo.r1pu
        elif vector_group == "Yzn":
            trafo.x0pu = np.random.uniform(0.07, 0.11) * trafo.x1pu
            trafo.r0pu = np.random.uniform(0.45, 0.54) * trafo.r1pu
        else:
            raise NotImplementedError("Vector class not supported")

        pf.SetWriteCacheEnabled(1)
        trafo.itapch = False
        trafo.iLimb = 3

        trafo.itrmt = 3
        psi0 = np.random.uniform(1.2, 1.25)
        xmair = np.random.uniform(1, 2) * trafo.uktr / 100
        xmlin = 1 / math.sqrt( (trafo.curmg / 100)**2 - (trafo.pfe / (trafo.strn*1000) )**2 )

        i, u = poly_to_rms_table(
            psi0=psi0,
            xmlin=xmlin,
            xmair=xmair,
            ksat=15,
            fnom=fn,
            v_min=1.2,
            v_max=1.5,
            n_points=13,
        )

        trafo.satcur = list(i)
        trafo.satflux = list(u)
        trafo.iInterPol = 1
        trafo.smoothfac = 10
        pf.WriteChangesToDb()
        pf.SetWriteCacheEnabled(0)


        if vector_group == "Yzn":
            if trafo.iLimb == 3:
                trafo.zx0hl_n = np.random.uniform(3, 10)
            elif trafo.iLimb == 5:
                trafo.zx0hl_n = np.random.uniform(10, 100)
            trafo.rtox0_n = 0

        pf.WriteChangesToDb()


def generate_110_20kV_trafo_lib(parent_lib, fn):
    grid_trafo_lib = get_pf_lib(parent_lib, "GridTrafos")
    grid_trafo_lib_110kV = get_pf_lib(grid_trafo_lib, "110/20kV")

    trafo_params = [
        {
            "sn": 20,
            "u_k": {"min": 0.1, "max": 0.12},
            "P_k": {"min": 95, "max": 100},
            "P_l": {"min": 14, "max": 16},
            "I_l": {"min": 0.004, "max": 0.005},
        },
        {
            "sn": 25,
            "u_k": {"min": 0.1, "max": 0.12},
            "P_k": {"min": 110, "max": 115},
            "P_l": {"min": 16, "max": 19},
            "I_l": {"min": 0.004, "max": 0.005}
        },
        {
            "sn": 31.5,
            "u_k": {"min": 0.1, "max": 0.13},
            "P_k": {"min": 130, "max": 135},
            "P_l": {"min": 19, "max": 23},
            "I_l": {"min": 0.004, "max": 0.0045}
        },
        {
            "sn": 40,
            "u_k": {"min": 0.1, "max": 0.15},
            "P_k": {"min": 155, "max": 160},
            "P_l": {"min": 23, "max": 27},
            "I_l": {"min": 0.0035, "max": 0.004}
        },
        {
            "sn": 50,
            "u_k": {"min": 0.13, "max": 0.158},
            "P_k": {"min": 190, "max": 190},
            "P_l": {"min": 32, "max": 32},
            "I_l": {"min": 0.0035, "max": 0.004}
        },
        {
            "sn": 63,
            "u_k": {"min": 0.13, "max": 0.16},
            "P_k": {"min": 220, "max": 220},
            "P_l": {"min": 38, "max": 38},
            "I_l": {"min": 0.0035, "max": 0.004}
        },
        {
            "sn": 80,
            "u_k": {"min": 0.14, "max": 0.16},
            "P_k": {"min": 260, "max": 260},
            "P_l": {"min": 45, "max": 45},
            "I_l": {"min": 0.0035, "max": 0.0035}
        }
    ]

    for i in range(1000):
        trafo_param_set = np.random.choice(trafo_params)
        sn = trafo_param_set["sn"]
        trafo = grid_trafo_lib_110kV.CreateObject("TypTr2", f"{sn} MVA 110/20 {fn} Hz Trafo{i}")

        trafo.strn = sn
        trafo.frnom = fn
        trafo.utrn_h = 110
        trafo.utrn_l = 20

        trafo.tr2cn_h = "YN"
        trafo.tr2cn_l = "D"
        trafo.nt2ag = np.random.choice([5.0, 11.0])

        trafo.uktr = np.random.uniform(trafo_param_set["u_k"]["min"], trafo_param_set["u_k"]["max"]) * 100
        trafo.pcutr = np.random.uniform(trafo_param_set["P_k"]["min"], trafo_param_set["P_k"]["max"])
        trafo.curmg = np.random.uniform(trafo_param_set["I_l"]["min"], trafo_param_set["I_l"]["max"]) * 100
        trafo.pfe = np.random.uniform(trafo_param_set["P_l"]["min"], trafo_param_set["P_l"]["max"])

        limbs = int(np.random.choice([3, 5]))
        trafo.iLimb = limbs
        if limbs == 3:
            trafo.x0pu = np.random.uniform(0.85, 1.0) * trafo.x1pu
            trafo.r0pu = np.random.uniform(1.5, 2.8) * trafo.r1pu
        elif limbs == 5:
            trafo.x0pu = np.random.uniform(0.95, 1.05) * trafo.x1pu
            trafo.r0pu = np.random.uniform(1.05, 1.1) * trafo.r1pu
        else:
            raise ValueError("Limbs must be 3 or 5")

        pf.SetWriteCacheEnabled(1)
        trafo.itapch = False
        trafo.itrmt = 3
        psi0 = np.random.uniform(1.2, 1.25)
        xmair = np.random.uniform(1, 2) * trafo.uktr / 100
        xmlin = 1 / math.sqrt( (trafo.curmg / 100)**2 - (trafo.pfe / (trafo.strn*1000) )**2 )

        i, u = poly_to_rms_table(
            psi0=psi0,
            xmlin=xmlin,
            xmair=xmair,
            ksat=15,
            fnom=fn,
            v_min=1.2,
            v_max=1.5,
            n_points=13,
        )

        trafo.satcur = list(i)
        trafo.satflux = list(u)
        trafo.iInterPol = 1
        trafo.smoothfac = 10
        pf.WriteChangesToDb()
        pf.SetWriteCacheEnabled(0)

def generate_110_11kV_trafo_lib(parent_lib, fn):
    grid_trafo_lib = get_pf_lib(parent_lib, "GridTrafos")
    grid_trafo_lib_110_11kV = get_pf_lib(grid_trafo_lib, "110/11kV")

    trafo_params = [
        {
            "sn": 20,
            "u_k": {"min": 0.1, "max": 0.12},
            "P_k": {"min": 95, "max": 100},
            "P_l": {"min": 14, "max": 16},
            "I_l": {"min": 0.004, "max": 0.005},
        },
    ]

    for i in range(1000):
        trafo_param_set = np.random.choice(trafo_params)
        sn = trafo_param_set["sn"]
        trafo = grid_trafo_lib_110_11kV.CreateObject("TypTr2", f"{sn} MVA 110/11 {fn} Hz Trafo{i}")

        trafo.strn = sn
        trafo.frnom = fn
        trafo.utrn_h = 110
        trafo.utrn_l = 11

        trafo.tr2cn_h = "YN"
        trafo.tr2cn_l = "D"
        trafo.nt2ag = np.random.choice([5.0, 11.0])

        trafo.uktr = np.random.uniform(trafo_param_set["u_k"]["min"], trafo_param_set["u_k"]["max"]) * 100
        trafo.pcutr = np.random.uniform(trafo_param_set["P_k"]["min"], trafo_param_set["P_k"]["max"])
        trafo.curmg = np.random.uniform(trafo_param_set["I_l"]["min"], trafo_param_set["I_l"]["max"]) * 100
        trafo.pfe = np.random.uniform(trafo_param_set["P_l"]["min"], trafo_param_set["P_l"]["max"])

        limbs = int(np.random.choice([3, 5]))
        trafo.iLimb = limbs
        if limbs == 3:
            trafo.x0pu = np.random.uniform(0.85, 1.0) * trafo.x1pu
            trafo.r0pu = np.random.uniform(1.5, 2.8) * trafo.r1pu
        elif limbs == 5:
            trafo.x0pu = np.random.uniform(0.95, 1.05) * trafo.x1pu
            trafo.r0pu = np.random.uniform(1.05, 1.1) * trafo.r1pu
        else:
            raise ValueError("Limbs must be 3 or 5")

        pf.SetWriteCacheEnabled(1)
        trafo.itapch = False
        trafo.itrmt = 3
        psi0 = np.random.uniform(1.2, 1.25)
        xmair = np.random.uniform(1, 2) * trafo.uktr / 100
        xmlin = 1 / math.sqrt( (trafo.curmg / 100)**2 - (trafo.pfe / (trafo.strn*1000) )**2 )

        i, u = poly_to_rms_table(
            psi0=psi0,
            xmlin=xmlin,
            xmair=xmair,
            ksat=15,
            fnom=fn,
            v_min=1.2,
            v_max=1.5,
            n_points=13,
        )

        trafo.satcur = list(i)
        trafo.satflux = list(u)
        trafo.iInterPol = 1
        trafo.smoothfac = 10
        pf.WriteChangesToDb()
        pf.SetWriteCacheEnabled(0)

def generate_380_110kV_trafo_lib(parent_lib, fn):
    grid_trafo_lib = get_pf_lib(parent_lib, "GridTrafos")
    grid_trafo_lib_380kV = get_pf_lib(grid_trafo_lib, "380/110kV")

    trafo_params = [
        {
            "sn": 100,
            "u_k": {"min": 0.14, "max": 0.16},
            "P_k": {"min": 0.35 * 100 * 1000/100, "max": 0.46 * 100 * 1000/100},
            "P_l": {"min": 0.04 * 100 * 1000/100, "max": 0.06 * 100 * 1000/100},
            "I_l": {"min": 0.0035, "max": 0.0046}
        },
        {
            "sn": 160,
            "u_k": {"min": 0.14, "max": 0.16},
            "P_k": {"min": 0.3 * 160 * 1000/100, "max": 0.35 * 160 * 1000/100},
            "P_l": {"min": 0.04 * 160 * 1000/100, "max": 0.06 * 160 * 1000/100},
            "I_l": {"min": 0.003, "max": 0.0035}
        },
        {
            "sn": 200,
            "u_k": {"min": 0.14, "max": 0.16},
            "P_k": {"min": 0.28 * 200 * 1000/100, "max": 0.35 * 200 * 1000/100},
            "P_l": {"min": 0.04 * 200 * 1000/100, "max": 0.06 * 200 * 1000/100},
            "I_l": {"min": 0.0028, "max": 0.0035}
        },
        {
            "sn": 250,
            "u_k": {"min": 0.15, "max": 0.17},
            "P_k": {"min": 0.26 * 250 * 1000/100, "max": 0.33 * 250 * 1000/100},
            "P_l": {"min": 0.04 * 250 * 1000/100, "max": 0.06 * 250 * 1000/100},
            "I_l": {"min": 0.0026, "max": 0.0033}
        },
        {
            "sn": 300,
            "u_k": {"min": 0.16, "max": 0.19},
            "P_k": {"min": 0.23 * 300 * 1000/100, "max": 0.31 * 300 * 1000/100},
            "P_l": {"min": 0.04 * 300 * 1000/100, "max": 0.06 * 300 * 1000/100},
            "I_l": {"min": 0.0023, "max": 0.0031}
        },
        {
            "sn": 400,
            "u_k": {"min": 0.16, "max": 0.20},
            "P_k": {"min": 0.21 * 400 * 1000/100, "max": 0.29 * 400 * 1000/100},
            "P_l": {"min": 0.04 * 400 * 1000/100, "max": 0.06 * 400 * 1000/100},
            "I_l": {"min": 0.0021, "max": 0.0029}
        },
        {
            "sn": 500,
            "u_k": {"min": 0.16, "max": 0.20},
            "P_k": {"min": 0.2 * 500 * 1000/100, "max": 0.28 * 500 * 1000/100},
            "P_l": {"min": 0.04 * 500 * 1000/100, "max": 0.06 * 500 * 1000/100},
            "I_l": {"min": 0.002, "max": 0.0028}
        }
    ]

    for i in range(1000):
        trafo_param_set = np.random.choice(trafo_params)
        sn = trafo_param_set["sn"]
        trafo = grid_trafo_lib_380kV.CreateObject("TypTr2", f"{sn} MVA 380/110 {fn} Hz Trafo{i}")


        trafo.strn = sn
        trafo.frnom = fn
        trafo.utrn_h = 380
        trafo.utrn_l = 110

        vector_group = "YNyn"
        trafo.tr2cn_h = "YN"
        trafo.tr2cn_l = "YN"
        trafo.nt2ag = 0

        trafo.uktr = np.random.uniform(trafo_param_set["u_k"]["min"], trafo_param_set["u_k"]["max"]) * 100
        trafo.pcutr = np.random.uniform(trafo_param_set["P_k"]["min"], trafo_param_set["P_k"]["max"])
        trafo.curmg = np.random.uniform(trafo_param_set["I_l"]["min"], trafo_param_set["I_l"]["max"]) * 100
        trafo.pfe = np.random.uniform(trafo_param_set["P_l"]["min"], trafo_param_set["P_l"]["max"])

        trafo.itapch = False
        trafo.iLimb = int(np.random.choice([3, 5]))

        delta_winding = np.random.choice([False, True])

        if trafo.iLimb == 3:
            if delta_winding:
                trafo.x0pu = np.random.uniform(1.8, 3.0) * trafo.x1pu
                trafo.r0pu = np.random.uniform(0.95, 1.05) * trafo.r1pu
            else:
                trafo.x0pu = np.random.uniform(5.0, 10) * trafo.x1pu
                trafo.r0pu = np.random.uniform(0.95, 1.05) * trafo.r1pu
        elif trafo.iLimb == 5:
            if delta_winding:
                trafo.x0pu = np.random.uniform(2.0, 5.0) * trafo.x1pu
                trafo.r0pu = np.random.uniform(0.95, 1.05) * trafo.r1pu
            else:
                trafo.x0pu = np.random.uniform(10.0, 100) * trafo.x1pu
                trafo.r0pu = np.random.uniform(0.95, 1.05) * trafo.r1pu
        else:
            raise NotImplementedError


        pf.SetWriteCacheEnabled(1)
        trafo.itrmt = 3
        psi0 = np.random.uniform(1.2, 1.25)
        xmair = np.random.uniform(1, 2) * trafo.uktr / 100
        xmlin = 1 / math.sqrt( (trafo.curmg / 100)**2 - (trafo.pfe / (trafo.strn*1000) )**2 )

        i, u = poly_to_rms_table(
            psi0=psi0,
            xmlin=xmlin,
            xmair=xmair,
            ksat=15,
            fnom=fn,
            v_min=1.2,
            v_max=1.5,
            n_points=13,
        )

        trafo.satcur = list(i)
        trafo.satflux = list(u)
        trafo.iInterPol = 1
        trafo.smoothfac = 10
        pf.WriteChangesToDb()
        pf.SetWriteCacheEnabled(0)

        if vector_group == "YNyn":
            # we assume an internal delta winding.
            if delta_winding:
                trafo.zx0hl_n = np.random.uniform(1, 2.4)
            else:
                if trafo.iLimb == 3:
                    trafo.zx0hl_n = np.random.uniform(3, 10)
                elif trafo.iLimb == 5:
                    trafo.zx0hl_n = np.random.uniform(10, 100)
            trafo.rtox0_n = 0

def generate_345_25kV_trafo_lib(parent_lib, fn):
    grid_trafo_lib = get_pf_lib(parent_lib, "GridTrafos")
    grid_trafo_lib_345kV = get_pf_lib(grid_trafo_lib, "345/25kV")

    trafo_params = [
        {
            "sn": 100,
            "u_k": {"min": 0.14, "max": 0.16},
            "P_k": {"min": 0.35 * 100 * 1000/100, "max": 0.46 * 100 * 1000/100},
            "P_l": {"min": 0.04 * 100 * 1000/100, "max": 0.06 * 100 * 1000/100},
            "I_l": {"min": 0.0035, "max": 0.0046}
        },
        {
            "sn": 160,
            "u_k": {"min": 0.14, "max": 0.16},
            "P_k": {"min": 0.3 * 160 * 1000/100, "max": 0.35 * 160 * 1000/100},
            "P_l": {"min": 0.04 * 160 * 1000/100, "max": 0.06 * 160 * 1000/100},
            "I_l": {"min": 0.003, "max": 0.0035}
        },
        {
            "sn": 200,
            "u_k": {"min": 0.14, "max": 0.16},
            "P_k": {"min": 0.28 * 200 * 1000/100, "max": 0.35 * 200 * 1000/100},
            "P_l": {"min": 0.04 * 200 * 1000/100, "max": 0.06 * 200 * 1000/100},
            "I_l": {"min": 0.0028, "max": 0.0035}
        },
        {
            "sn": 250,
            "u_k": {"min": 0.15, "max": 0.17},
            "P_k": {"min": 0.26 * 250 * 1000/100, "max": 0.33 * 250 * 1000/100},
            "P_l": {"min": 0.04 * 250 * 1000/100, "max": 0.06 * 250 * 1000/100},
            "I_l": {"min": 0.0026, "max": 0.0033}
        },
        {
            "sn": 300,
            "u_k": {"min": 0.16, "max": 0.19},
            "P_k": {"min": 0.23 * 300 * 1000/100, "max": 0.31 * 300 * 1000/100},
            "P_l": {"min": 0.04 * 300 * 1000/100, "max": 0.06 * 300 * 1000/100},
            "I_l": {"min": 0.0023, "max": 0.0031}
        },
        {
            "sn": 400,
            "u_k": {"min": 0.16, "max": 0.20},
            "P_k": {"min": 0.21 * 400 * 1000/100, "max": 0.29 * 400 * 1000/100},
            "P_l": {"min": 0.04 * 400 * 1000/100, "max": 0.06 * 400 * 1000/100},
            "I_l": {"min": 0.0021, "max": 0.0029}
        },
        {
            "sn": 500,
            "u_k": {"min": 0.16, "max": 0.20},
            "P_k": {"min": 0.2 * 500 * 1000/100, "max": 0.28 * 500 * 1000/100},
            "P_l": {"min": 0.04 * 500 * 1000/100, "max": 0.06 * 500 * 1000/100},
            "I_l": {"min": 0.002, "max": 0.0028}
        },
        {
            "sn": 600,
            "u_k": {"min": 0.16, "max": 0.20},
            "P_k": {"min": 0.2 * 600 * 1000/100, "max": 0.28 * 600 * 1000/100},
            "P_l": {"min": 0.04 * 600 * 1000/100, "max": 0.06 * 600 * 1000/100},
            "I_l": {"min": 0.002, "max": 0.0028}
        },
        {
            "sn": 800,
            "u_k": {"min": 0.16, "max": 0.20},
            "P_k": {"min": 0.18 * 800 * 1000/100, "max": 0.26 * 800 * 1000/100},
            "P_l": {"min": 0.04 * 800 * 1000/100, "max": 0.06 * 800 * 1000/100},
            "I_l": {"min": 0.0018, "max": 0.0026}
        },
    ]

    for i in range(1000):
        trafo_param_set = np.random.choice(trafo_params)
        sn = trafo_param_set["sn"]
        if sn <= 50:
            limbs = 3
            x0tox1 = np.random.uniform(0.85, 1.0)
            r0tor1 = np.random.uniform(1.0, 3.0)
        elif sn <= 350:
            limbs = 3
            x0tox1 = np.random.uniform(0.85, 0.95)
            r0tor1 = np.random.uniform(1.8, 2.0)
        else:
            limbs = 5
            x0tox1 = np.random.uniform(0.95, 1.05)
            r0tor1 = np.random.uniform(1.0, 1.1)

        utrn_h = 345
        utrn_l = 25

        trafo = grid_trafo_lib_345kV.CreateObject("TypTr2", f"{sn} MVA {utrn_h}/{utrn_l} {fn} Hz Trafo{i}")


        trafo.strn = sn
        trafo.frnom = fn
        trafo.utrn_h = utrn_h
        trafo.utrn_l = utrn_l

        trafo.tr2cn_h = "YN"
        trafo.tr2cn_l = "D"
        trafo.nt2ag = np.random.choice([5.0, 11.0])

        trafo.uktr = np.random.uniform(trafo_param_set["u_k"]["min"], trafo_param_set["u_k"]["max"]) * 100
        trafo.pcutr = np.random.uniform(trafo_param_set["P_k"]["min"], trafo_param_set["P_k"]["max"])
        trafo.curmg = np.random.uniform(trafo_param_set["I_l"]["min"], trafo_param_set["I_l"]["max"]) * 100
        trafo.pfe = np.random.uniform(trafo_param_set["P_l"]["min"], trafo_param_set["P_l"]["max"])

        trafo.iLimb = limbs
        trafo.x0pu = x0tox1 * trafo.x1pu
        trafo.r0pu = r0tor1 * trafo.r1pu

        pf.SetWriteCacheEnabled(1)
        trafo.itapch = False
        trafo.itrmt = 3
        psi0 = np.random.uniform(1.2, 1.25)
        xmair = np.random.uniform(1, 2) * trafo.uktr / 100
        xmlin = 1 / math.sqrt( (trafo.curmg / 100)**2 - (trafo.pfe / (trafo.strn*1000) )**2 )

        i, u = poly_to_rms_table(
            psi0=psi0,
            xmlin=xmlin,
            xmair=xmair,
            ksat=15,
            fnom=fn,
            v_min=1.2,
            v_max=1.5,
            n_points=13,
        )

        trafo.satcur = list(i)
        trafo.satflux = list(u)
        trafo.iInterPol = 1
        trafo.smoothfac = 10
        pf.WriteChangesToDb()
        pf.SetWriteCacheEnabled(0)

def generate_block_trafos(parent_lib, fn):
    block_trafo_lib = get_pf_lib(parent_lib, "MachineTrafos")

    trafo_params = [
        {
            "sn": 20,
            "u_k": {"min": 0.1, "max": 0.12},
            "P_k": {"min": 95, "max": 100},
            "P_l": {"min": 14, "max": 16},
            "I_l": {"min": 0.004, "max": 0.005},
        },
        {
            "sn": 25,
            "u_k": {"min": 0.1, "max": 0.12},
            "P_k": {"min": 110, "max": 115},
            "P_l": {"min": 16, "max": 19},
            "I_l": {"min": 0.004, "max": 0.005}
        },
        {
            "sn": 31.5,
            "u_k": {"min": 0.1, "max": 0.13},
            "P_k": {"min": 130, "max": 135},
            "P_l": {"min": 19, "max": 23},
            "I_l": {"min": 0.004, "max": 0.0045}
        },
        {
            "sn": 40,
            "u_k": {"min": 0.1, "max": 0.15},
            "P_k": {"min": 155, "max": 160},
            "P_l": {"min": 23, "max": 27},
            "I_l": {"min": 0.0035, "max": 0.004}
        },
        {
            "sn": 50,
            "u_k": {"min": 0.13, "max": 0.158},
            "P_k": {"min": 190, "max": 190},
            "P_l": {"min": 32, "max": 32},
            "I_l": {"min": 0.0035, "max": 0.004}
        },
        {
            "sn": 63,
            "u_k": {"min": 0.13, "max": 0.16},
            "P_k": {"min": 220, "max": 220},
            "P_l": {"min": 38, "max": 38},
            "I_l": {"min": 0.0035, "max": 0.004}
        },
        {
            "sn": 80,
            "u_k": {"min": 0.14, "max": 0.16},
            "P_k": {"min": 260, "max": 260},
            "P_l": {"min": 45, "max": 45},
            "I_l": {"min": 0.0035, "max": 0.0035}
        },
        {
            "sn": 100,
            "u_k": {"min": 0.14, "max": 0.16},
            "P_k": {"min": 0.35 * 100 * 1000/100, "max": 0.46 * 100 * 1000/100},
            "P_l": {"min": 0.04 * 100 * 1000/100, "max": 0.06 * 100 * 1000/100},
            "I_l": {"min": 0.0035, "max": 0.0046}
        },
        {
            "sn": 160,
            "u_k": {"min": 0.14, "max": 0.16},
            "P_k": {"min": 0.3 * 160 * 1000/100, "max": 0.35 * 160 * 1000/100},
            "P_l": {"min": 0.04 * 160 * 1000/100, "max": 0.06 * 160 * 1000/100},
            "I_l": {"min": 0.003, "max": 0.0035}
        },
        {
            "sn": 200,
            "u_k": {"min": 0.14, "max": 0.16},
            "P_k": {"min": 0.28 * 200 * 1000/100, "max": 0.35 * 200 * 1000/100},
            "P_l": {"min": 0.04 * 200 * 1000/100, "max": 0.06 * 200 * 1000/100},
            "I_l": {"min": 0.0028, "max": 0.0035}
        },
        {
            "sn": 250,
            "u_k": {"min": 0.15, "max": 0.17},
            "P_k": {"min": 0.26 * 250 * 1000/100, "max": 0.33 * 250 * 1000/100},
            "P_l": {"min": 0.04 * 250 * 1000/100, "max": 0.06 * 250 * 1000/100},
            "I_l": {"min": 0.0026, "max": 0.0033}
        },
        {
            "sn": 300,
            "u_k": {"min": 0.16, "max": 0.19},
            "P_k": {"min": 0.23 * 300 * 1000/100, "max": 0.31 * 300 * 1000/100},
            "P_l": {"min": 0.04 * 300 * 1000/100, "max": 0.06 * 300 * 1000/100},
            "I_l": {"min": 0.0023, "max": 0.0031}
        },
        {
            "sn": 400,
            "u_k": {"min": 0.16, "max": 0.20},
            "P_k": {"min": 0.21 * 400 * 1000/100, "max": 0.29 * 400 * 1000/100},
            "P_l": {"min": 0.04 * 400 * 1000/100, "max": 0.06 * 400 * 1000/100},
            "I_l": {"min": 0.0021, "max": 0.0029}
        },
        {
            "sn": 500,
            "u_k": {"min": 0.16, "max": 0.20},
            "P_k": {"min": 0.2 * 500 * 1000/100, "max": 0.28 * 500 * 1000/100},
            "P_l": {"min": 0.04 * 500 * 1000/100, "max": 0.06 * 500 * 1000/100},
            "I_l": {"min": 0.002, "max": 0.0028}
        },
        {
            "sn": 600,
            "u_k": {"min": 0.16, "max": 0.20},
            "P_k": {"min": 0.2 * 600 * 1000/100, "max": 0.28 * 600 * 1000/100},
            "P_l": {"min": 0.04 * 600 * 1000/100, "max": 0.06 * 600 * 1000/100},
            "I_l": {"min": 0.002, "max": 0.0028}
        },
        {
            "sn": 800,
            "u_k": {"min": 0.16, "max": 0.20},
            "P_k": {"min": 0.18 * 800 * 1000/100, "max": 0.26 * 800 * 1000/100},
            "P_l": {"min": 0.04 * 800 * 1000/100, "max": 0.06 * 800 * 1000/100},
            "I_l": {"min": 0.0018, "max": 0.0026}
        },
        {
            "sn": 1000,
            "u_k": {"min": 0.16, "max": 0.20},
            "P_k": {"min": 0.16 * 1000 * 1000/100, "max": 0.24 * 1000 * 1000/100},
            "P_l": {"min": 0.04 * 1000 * 1000/100, "max": 0.06 * 1000 * 1000/100},
            "I_l": {"min": 0.0016, "max": 0.0024}
        },
        {
            "sn": 1200,
            "u_k": {"min": 0.16, "max": 0.20},
            "P_k": {"min": 0.14 * 1200 * 1000/100, "max": 0.22 * 1200 * 1000/100},
            "P_l": {"min": 0.04 * 1200 * 1000/100, "max": 0.06 * 1200 * 1000/100},
            "I_l": {"min": 0.0014, "max": 0.0022}
        },
    ]

    for i in range(4000):
        trafo_param_set = np.random.choice(trafo_params)
        sn = trafo_param_set["sn"]
        if sn <= 40:
            utrn_h = 110.0
            utrn_l = 6.3
            limbs = 3
            x0tox1 = np.random.uniform(0.85, 1.0)
            r0tor1 = np.random.uniform(1.0, 3.0)
        elif sn <= 200:
            utrn_h = np.random.choice([110.0, 345.0])
            utrn_l = 10.5
            limbs = 3
            if utrn_h == 110:
                x0tox1 = np.random.uniform(0.85, 1.0)
                r0tor1 = np.random.uniform(1.5, 2.8)
            elif utrn_h == 345:
                x0tox1 = np.random.uniform(0.85, 0.95)
                r0tor1 = np.random.uniform(1.8, 2.0)
            else:
                raise NotImplementedError("Not implemented")

        elif sn <= 800:
            limbs = 5
            utrn_h = 345.0
            utrn_l = 21
            x0tox1 = np.random.uniform(0.95, 1.05)
            r0tor1 = np.random.uniform(1.0, 1.1)
        else:
            limbs = 5
            utrn_h = 345.0
            utrn_l = 27
            x0tox1 = np.random.uniform(0.95, 1.05)
            r0tor1 = np.random.uniform(1.0, 1.1)

        trafo = block_trafo_lib.CreateObject("TypTr2", f"{sn} MVA {utrn_h}/{utrn_l} {fn} Hz Trafo{i}")

        trafo.strn = sn
        trafo.frnom = fn
        trafo.utrn_h = utrn_h
        trafo.utrn_l = utrn_l

        trafo.tr2cn_h = "YN"
        trafo.tr2cn_l = "D"
        trafo.nt2ag = np.random.choice([5.0, 11.0])

        trafo.uktr = np.random.uniform(trafo_param_set["u_k"]["min"], trafo_param_set["u_k"]["max"]) * 100
        trafo.pcutr = np.random.uniform(trafo_param_set["P_k"]["min"], trafo_param_set["P_k"]["max"])
        trafo.curmg = np.random.uniform(trafo_param_set["I_l"]["min"], trafo_param_set["I_l"]["max"]) * 100
        trafo.pfe = np.random.uniform(trafo_param_set["P_l"]["min"], trafo_param_set["P_l"]["max"])

        trafo.iLimb = limbs
        trafo.x0pu = x0tox1 * trafo.x1pu
        trafo.r0pu = r0tor1 * trafo.r1pu

        pf.SetWriteCacheEnabled(1)
        trafo.itapch = False
        trafo.itrmt = 3
        psi0 = np.random.uniform(1.2, 1.25)
        xmair = np.random.uniform(1, 2) * trafo.uktr / 100
        xmlin = 1 / math.sqrt( (trafo.curmg / 100)**2 - (trafo.pfe / (trafo.strn*1000) )**2 )

        i, u = poly_to_rms_table(
            psi0=psi0,
            xmlin=xmlin,
            xmair=xmair,
            ksat=15,
            fnom=fn,
            v_min=1.2,
            v_max=1.5,
            n_points=13,
        )
        trafo.satcur = list(i)
        trafo.satflux = list(u)
        trafo.iInterPol = 1
        trafo.smoothfac = 10
        pf.WriteChangesToDb()
        pf.SetWriteCacheEnabled(0)


print("Note: Input Options shall be: trafo.iopt_uk = 'pcu', trafo.iopt_uk0 = 'r0x0'")

user = pf.GetCurrentUser()
input_options = user.GetContents("Settings 2-Winding Transformer.OptTyptr2", 1)[0]
assert input_options.iopt_uk == "pcu"
assert input_options.iopt_uk0 == "r0x0"

main_lib = get_pf_lib(user, "CustomTypeLib")


trafo_types = main_lib.GetContents("*.TypTr2", 1)
for trafo in trafo_types:
    trafo.Delete()

for fn in [50, 60]:
    trafo_type_lib = get_pf_lib(main_lib, "TrafoTypes")
    freq_lib = get_pf_lib(trafo_type_lib, f"{fn}Hz")

    generate_20_04kV_trafo_lib(freq_lib, fn)
    generate_110_20kV_trafo_lib(freq_lib, fn)
    generate_110_11kV_trafo_lib(freq_lib, fn)
    generate_380_110kV_trafo_lib(freq_lib, fn)
    generate_345_25kV_trafo_lib(freq_lib, fn)
    generate_block_trafos(freq_lib, fn)

print("Trafo Lib successfully completed.")
print()
