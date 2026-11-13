import numpy as np

from util.pf_utils import get_pf_lib

np.random.seed(0)

import powerfactory
pf = powerfactory.GetApplicationExt()
# pf.Show()

user = pf.GetCurrentUser()
parent_lib = get_pf_lib(user, "CustomTypeLib")

load_lib = get_pf_lib(parent_lib, "LoadTypes")


# Delete old cables
load_types = parent_lib.GetContents("*.TypLod", 1)
for load_type in load_types:
    load_type.Delete()


min_max = {
    'kP,Z': (0.20, 1.31),
    'kP,I': (-1.14, 0.50),
    'kP,P': (0.14, 0.83),
    'kQ,Z': (0.43, 4.74),
    'kQ,I': (-6.19, 0.71),
    'kQ,P': (-0.14, 2.45)
}

def sample_and_normalize():
    while True:
        kP_Z = np.random.uniform(*min_max['kP,Z'])
        kP_I = np.random.uniform(*min_max['kP,I'])
        kP_P = np.random.uniform(*min_max['kP,P'])
        kQ_Z = np.random.uniform(*min_max['kQ,Z'])
        kQ_I = np.random.uniform(*min_max['kQ,I'])
        kQ_P = np.random.uniform(*min_max['kQ,P'])

        sum_kP = kP_Z + kP_I + kP_P
        kP_Z /= sum_kP
        kP_I /= sum_kP
        kP_P /= sum_kP

        sum_kQ = kQ_Z + kQ_I + kQ_P
        kQ_Z /= sum_kQ
        kQ_I /= sum_kQ
        kQ_P /= sum_kQ

        # check if all values lie within the predefined thresholds
        if (min_max['kP,Z'][0] <= kP_Z <= min_max['kP,Z'][1] and
            min_max['kP,I'][0] <= kP_I <= min_max['kP,I'][1] and
            min_max['kP,P'][0] <= kP_P <= min_max['kP,P'][1] and
            min_max['kQ,Z'][0] <= kQ_Z <= min_max['kQ,Z'][1] and
            min_max['kQ,I'][0] <= kQ_I <= min_max['kQ,I'][1] and
            min_max['kQ,P'][0] <= kQ_P <= min_max['kQ,P'][1]):
            break

    return kP_Z, kP_I, kP_P, kQ_Z, kQ_I, kQ_P


for i in range(1000):
    pf.SetWriteCacheEnabled(1)
    load = load_lib.CreateObject("TypLod", f"Load{i}")

    load.kpu0 = 2
    load.kpu1 = 1
    load.kpu = 0

    load.kqu0 = 2
    load.kqu1 = 1
    load.kqu = 0

    kP_Z, kP_I, kP_P, kQ_Z, kQ_I, kQ_P = sample_and_normalize()

    load.aP = kP_Z
    load.bP = kP_I

    load.aQ = kQ_Z
    load.bQ = kQ_I

    pf.WriteChangesToDb()
    pf.SetWriteCacheEnabled(0)

    assert abs(load.cQ - kQ_P) < 0.001 and abs(load.cP - kP_P) < 0.001



print("Load Lib successfully completed.")

