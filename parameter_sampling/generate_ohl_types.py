import numpy as np

from util.pf_utils import get_pf_lib

np.random.seed(0)

import powerfactory
pf = powerfactory.GetApplicationExt()
# pf.Show()

user = pf.GetCurrentUser()
parent_lib = get_pf_lib(user, "CustomTypeLib")

ohl_type_lib = get_pf_lib(parent_lib, "OHLTypes")



def get_20kV_tower_data():
    arrangement = np.random.choice(['flat', 'vertical'])

    conductor_height_at_tower_lowest = np.random.uniform(9.5, 14) # meters
    conductor_height_lowest_sag = np.random.uniform(6, 0.9 * conductor_height_at_tower_lowest)
    conductor_sag = conductor_height_at_tower_lowest - conductor_height_lowest_sag
    conductor_dist = np.random.uniform(1.4, 2.2)
    conductor_average_height = conductor_height_at_tower_lowest - 2 / 3 * conductor_sag

    if arrangement == 'flat':
        y1 = conductor_average_height
        y2 = conductor_average_height + np.random.uniform(0, 1)  # middle one might be higher
        y3 = conductor_average_height
        x1 = -conductor_dist
        x2 = 0
        x3 = conductor_dist
    else:
        y1 = conductor_average_height
        y2 = conductor_average_height + conductor_dist
        y3 = conductor_average_height + 2 * conductor_dist
        x1 = 0
        x2 = np.random.uniform(0, 1)
        x3 = 0

    return [x1, x2, x3], [y1, y2, y3], arrangement


def get_hv_tower_data(vn):
    if vn == 110:
        ch_min, ch_max = 19, 28
        ch_lsag_min = 6
        c_dist_min, c_dist_max = 3, 4.7
        x_earth_min, x_earth_max = 3.2, 5
        y_earth_min, y_earth_max = 4, 5
    elif vn == 345:
        ch_min, ch_max = 22, 60
        ch_lsag_min = 7.8
        c_dist_min, c_dist_max = 6, 11
        x_earth_min, x_earth_max = 7, 8
        y_earth_min, y_earth_max = 8, 15
    else:
        raise NotImplementedError

    xearth2, yearth2 = None, None
    arrangement = np.random.choice(['danube', 'fork', 'stower', 'flat', 'flat2e'])

    conductor_height_at_tower_lowest = np.random.uniform(ch_min, ch_max) # meters
    conductor_height_lowest_sag = np.random.uniform(ch_lsag_min, 0.9 * conductor_height_at_tower_lowest)
    conductor_sag = conductor_height_at_tower_lowest - conductor_height_lowest_sag
    conductor_dist = np.random.uniform(c_dist_min, c_dist_max)
    conductor_average_height = conductor_height_at_tower_lowest - 2 / 3 * conductor_sag

    if arrangement == 'danube':
        angle = np.random.uniform(60, 90)
        deltax = np.cos(np.radians(angle)) * conductor_dist
        deltay = np.sin(np.radians(angle)) * conductor_dist

        y1 = conductor_average_height
        y2 = conductor_average_height
        y3 = conductor_average_height + deltay
        x1 = 0
        x2 = conductor_dist
        x3 = conductor_dist - deltax

        xearth = x2 + np.random.uniform(x_earth_min, x_earth_max)
        yearth = y3 + np.random.uniform(y_earth_min, y_earth_max)

    elif arrangement == 'fork':
        y1 = conductor_average_height
        y2 = conductor_average_height + conductor_dist
        y3 = conductor_average_height + 2 * conductor_dist
        x1 = 0
        x2 = np.random.uniform(0, 1)
        x3 = 0

        xearth = x2 - np.random.uniform(x_earth_min, x_earth_max)
        yearth = y3 + np.random.uniform(y_earth_min, y_earth_max)

    elif arrangement == 'stower':
        deltax = np.cos(np.radians(30)) * conductor_dist
        deltay = np.sin(np.radians(30)) * conductor_dist

        y1 = conductor_average_height
        y2 = conductor_average_height + conductor_dist
        y3 = conductor_average_height + deltay
        x1 = 0
        x2 = 0
        x3 = deltax

        xearth = deltax / 2
        yearth = y2 + np.random.uniform(y_earth_min, y_earth_max)


    elif arrangement == 'flat':
        y1 = conductor_average_height
        y2 = conductor_average_height
        y3 = conductor_average_height
        x1 = -conductor_dist
        x2 = 0
        x3 = conductor_dist

        xearth = x3 + np.random.uniform(x_earth_min, x_earth_max)
        yearth = y3 + np.random.uniform(y_earth_min, y_earth_max)


    elif arrangement == 'flat2e':  # flat2e
        y1 = conductor_average_height
        y2 = conductor_average_height
        y3 = conductor_average_height
        x1 = -conductor_dist
        x2 = 0
        x3 = conductor_dist

        xearth = -conductor_dist / 2
        yearth = y3 + np.random.uniform(y_earth_min, y_earth_max)

        xearth2 = conductor_dist / 2
        yearth2 = yearth

    else:
        raise NotImplementedError

    return [x1, x2, x3], [y1, y2, y3], [xearth, yearth], [xearth2, yearth2], arrangement


# Delete old cables
towers = parent_lib.GetContents("*.TypTow", 1)
for tower in towers:
    tower.Delete()

for fn in [50, 60]:
    for voltage in [20, 110, 345]:
        conductor_lib = get_pf_lib(parent_lib, "Conductors")
        conductor_lib_vn = get_pf_lib(conductor_lib, f"{voltage}kV")
        all_earth_conductor_lib = get_pf_lib(conductor_lib, "Earthwires")
        earth_conductor_lib = get_pf_lib(all_earth_conductor_lib, f"{voltage}kV")

        fn_lib = get_pf_lib(ohl_type_lib, f"{fn}Hz")
        vn_lib = get_pf_lib(fn_lib, f"{voltage}kV")

        for i in range(1000):
            pf.SetWriteCacheEnabled(1)
            tower = vn_lib.CreateObject("TypTow", f"{voltage}kV Tower{i}")
            tower.frnom = fn  # frequency at which the line parameters are calculated (PowerFactory default: 50 Hz)
            tower.nlcir = 1
            tower.pcond_c = [np.random.choice(conductor_lib_vn.GetContents("*.TypCon", 1))]
            tower.rearth = np.random.uniform(5, 500)

            if voltage == 20:
                tower.nlear = 0
                tower.iTransMode = int(np.random.choice([0, 3]))
                tower.gshunt = np.random.uniform(1.5*10**(-12), 3.7*10**(-9)) * 10**6
                x, y, arrangement = get_20kV_tower_data()
                tower.loc_name = f"{voltage}kV {arrangement} Tower{i}"
            else:
                # HV Tower
                tower.iTransMode = 3  # high voltage are usually drilled.
                if voltage == 110:
                    tower.gshunt = np.random.uniform(1.5*10**(-12), 3.7*10**(-9)) * 10**6
                elif voltage == 345:
                    tower.gshunt = np.random.uniform(1.5*10**(-12), 3.7*10**(-9)) * 10**6
                else:
                    raise NotImplementedError

                tower.pcond_c = [np.random.choice(conductor_lib_vn.GetContents("*.TypCon", 1))]
                x, y, earth1, earth2, arrangement = get_hv_tower_data(voltage)
                tower.loc_name = f"{voltage}kV {arrangement} Tower{i}"

                if earth2[0] is not None:
                    tower.nlear = 2
                    tower.xy_e = [earth1, earth2]
                    earth_conductor = np.random.choice(earth_conductor_lib.GetContents("*.TypCon", 1))
                    tower.pcond_e = [earth_conductor, earth_conductor]
                else:
                    tower.nlear = 1
                    tower.xy_e = [earth1]
                    tower.pcond_e = [np.random.choice(earth_conductor_lib.GetContents("*.TypCon", 1))]

            phs_order = [0, 1, 2]
            np.random.shuffle(phs_order)
            xy_c = [
                x[int(phs_order[0])],
                x[int(phs_order[1])],
                x[int(phs_order[2])],
                y[int(phs_order[0])],
                y[int(phs_order[1])],
                y[int(phs_order[2])]
            ]
            tower.SetAttribute("xy_c", [xy_c])

            pf.WriteChangesToDb()
            pf.SetWriteCacheEnabled(0)



print("OHL Lib successfully completed.")

