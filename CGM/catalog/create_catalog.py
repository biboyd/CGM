import numpy as np
import yt
import salsa
from mpi4py import MPI
import argparse


from CGM.general_utils.filter_definitions import default_ice_fields, default_units_dict, default_cloud_dict, parse_cut_filter

from sys import path 
path.insert(0,"/mnt/home/boydbre1/Repo/foggie")
from foggie.utils.foggie_load import foggie_load

"""
File for generating an absorber catalog in the same vein as in
extract_sample_absorber, but using salsa package :)
"""

def main(args):

    ds_filename= args.ds
    n_rays = args.n_rays
    raydir = args.raydir
    ion = args.ion
    rlength = args.rlength
    max_imp = args.max_impact
    cuts = args.cut

    outfile = args.outfile


    # set rand seed 
    np.random.seed(2020 + 16*int(ds_filename[-2:]))
    comm = MPI.COMM_WORLD

    #load dataset using foggie
    box_trackfile = '/mnt/home/boydbre1/data/track_files/halo_track_200kpc_nref10' #might want to make more flexible
    hcv_file='/mnt/home/boydbre1/Repo/foggie/foggie/halo_infos/008508/nref11c_nref9f/halo_c_v'
    ds, reg_foggie = foggie_load(ds_filename, box_trackfile,
                                 halo_c_v_name=hcv_file, disk_relative=True)

    # broadcast dataset to each process
    comm.Barrier()

    cut_filters= parse_cut_filter(cuts)
    ext_kwargs = {'absorber_min':default_cloud_dict[ion]}

    df = salsa.generate_catalog(ds, n_rays, raydir, [ion],
                                center=ds.halo_center_code,
                                impact_param_lims=(0, max_imp),
                                cut_region_filters=cut_filters,
                                ray_length=rlength, fields=default_ice_fields,
                                extractor_kwargs=ext_kwargs,
                                units_dict=default_units_dict)

    #now save it
    if comm.rank == 0:
        df.to_csv(outfile)

if __name__ == '__main__':
    #create parser
    parser = argparse.ArgumentParser(description='Process cuts and stuff')
    parser.add_argument("--ds", type=str, help="The dataset path",
                        required=True)
    parser.add_argument("--raydir", type=str, help="path to dir where rays are/will be saved",
                        required=True)
    parser.add_argument("-o","--outfile", type=str, help="filename where catalog is saved",
                        required=True)
    parser.add_argument("-i", "--ion", type=str,
                        help='The ion to look at (ie "H I", "O VI")',
                        required=True)
    parser.add_argument("-m", "--max-impact", type=int,
                        help="Max impact parameter sampled", default=200)
    parser.add_argument("-c", "--cut", type=str, default='cgm')

    parser.add_argument("-n", "--n-rays", type=int, help="number of rays to create",
                        default=10)

    parser.add_argument("-l", "--rlength", type=int, help="length of lray in kpc",
                            default=200)



    args=parser.parse_args()

    main(args)
