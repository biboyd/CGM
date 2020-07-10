import numpy as np
import yt
from astropy.table import Table
import sys

from CGM.general_utils.filter_definitions import parse_cut_filter

def main(df_file,raydir, cut_str, outdir):

    # load dataframe
    df = pd.read_csv(df_file, index_col=0)

    #extract all the x/y/z postions for each cell in an absorber
    positions =[]
    for index, s, e in df[['absorber_index', 'interval_start', 'interval_end']]:
        ray_num=index[:-1]

        ray = yt.load(f"{raydir}/ray{ray_num}.h5")

        cut_filters = parse_cut_filter(cut_str)

        data = ray.all_data()
        for fil in cut_filters:
            data = data.cut_region(fil)

        coords, =np.dstack([data['x'][s:e].in_units('code_length'),
                            data['y'][s:e].in_units('code_length'),
                            data['z'][s:e].in_units('code_length')])

        positions.append(coords)

        ray.close()

    #output as a numpy array
    all_positions = np.vstack(positions)

    return all_positions


if __name__ == '__main__':
    ds=sys.argv[1]

    data_dir="/mnt/home/boydbre1/data/absorber_data/cool_refinement/max_impact200/ion_O_VI/"
    df_file = f"{data_dir}/cgm/{ds}_absorbers.csv"
    raydir=f"/mnt/gs18/scratch/users/boydbre1/analysis/cool_refinement/{ds}/max_impact200/rays/"

    pos = main(df_file, raydir, "cgm", data_dir)
    np.save(f"{data_dir}/cgm/{ds}_positions.npy", pos)
