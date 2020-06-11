import yt
import trident
import numpy as np

from mpi4py import MPI
from sys import argv, path
from os import makedirs
from scipy.spatial.transform import Rotation
import matplotlib.pyplot as plt

from CGM.general_utils.construct_rays import construct_rays
from CGM.general_utils.center_finder import find_center
from CGM.general_utils.filter_definitions import radius_function, ion_p, default_ice_fields

path.insert(0,"/mnt/home/boydbre1/Repo/foggie")
from foggie.utils.foggie_load import foggie_load

def random_sightlines(dsname, center, num_sightlines, max_impact_param, min_impact_param=0, length=200, seed=None):
    """
    randomly sample impact parameter to get random sightlines from a given galaxy center

    Parameters:
        center : arr: coordinates of the center of the galaxy
        num_sightlines : int : number of sightlines to return
        max_impact_param : float : maximum impact param to sample from in kpc
        min_impact_param : float : minimum impact param to sample from in kpc
        length : float : length of the sightline in kpc

    Returns :
        start_points : array : 2d array of the startpoints for
                    each sightline
        end_points : array : 2d array of the endpoints for
                    each sightline
    """
    # define random seed, put length properties in code_length
    np.random.seed(seed)
    ds = yt.load(dsname)
    length = ds.quan(length, 'kpc').in_units('code_length')
    length = length.value
    min_impact_param = ds.quan(min_impact_param, 'kpc').in_units('code_length')
    max_impact_param = ds.quan(max_impact_param, 'kpc').in_units('code_length')

    #randomly select angle and distance from center of gal
    #take sqrt so that impact param is uniform in projected area space
    impact_param = np.sqrt(np.random.uniform(min_impact_param.value**2, max_impact_param.value**2, num_sightlines))

    #theta represents polar angle. phi represents azimuthal
    theta = np.random.uniform(0, np.pi, num_sightlines)
    phi = np.random.uniform(0, 2*np.pi, num_sightlines)

    #construct vector from gal_center to sightline midpoint
    rad_vec= np.empty((num_sightlines, 3))
    rad_vec[:, 0] = impact_param*np.cos(phi)*np.sin(theta)
    rad_vec[:, 1] = impact_param*np.sin(phi)*np.sin(theta)
    rad_vec[:, 2] = impact_param*np.cos(theta)

    #define vector along sightline (perpendicular to radial vector)
    perp_vec = np.empty_like(rad_vec)
    perp_vec[:, 0] = rad_vec[:, 1]
    perp_vec[:, 1] = -1*rad_vec[:, 0]
    perp_vec[:, 2] = 0.

    #randomly rotate perp_vec around rad vec
    alpha=np.random.uniform(0., 2*np.pi, num_sightlines)
    for i in range(num_sightlines):
        #normalize perpendicular vector
        perp_vec[i, :] =  perp_vec[i, :]/np.sqrt(perp_vec[i, 0]**2 + perp_vec[i, 1]**2)
        #rotate around radial vector by random amount
        rot_vec = alpha[i] *rad_vec[i, :]/np.linalg.norm(rad_vec[i, :])
        rot = Rotation.from_rotvec(rot_vec)
        perp_vec[i, :] = rot.apply(perp_vec[i, :])


    #shift to be centered at galaxy
    sightline_centers = rad_vec +np.array(center)

    #find ending and start points for each sightline
    end_point = sightline_centers + length/2 *perp_vec
    start_point = sightline_centers - length/2 *perp_vec

    return start_point, end_point, impact_param

def random_rays(dsname, center,
                n_rays, max_impact_param,
                min_impact_param=0.,
                length=200,
                bulk_velocity=None,
                line_list=['H I', 'C IV', 'O VI'],
                other_fields=None,
                use_foggie_load=True,
                out_dir='./',
                parallel=True,
                seed=None):
    """

    Parameters:
        dsname : string : path to dataset
        center : arr: coordinates of the center of the galaxy
        n_rays : int : number of light rays to construct
        max_impact_param : float : maximum impact param to sample from in kpc
        min_impact_param : float : minimum impact param to sample from in kpc
        length : float : length of the sightline in kpc
        line_list : list : ions to add to lightray
        other_fields : list : fields to add to lightray
        out_dir : string : path to where ray files will be written
        parallel : bool : runs in parallel by evenly dividing rays to processes
        seed : int : seed to use in random number generate. If None, then seed will
            be chosen randomly by numpy

    Returns:
        none
    """

    # get start/end points for light rays
    if use_foggie_load:
        box_trackfile = '/mnt/home/boydbre1/data/track_files/halo_track_200kpc_nref10' #might want to make more flexible
        ds, reg_foggie = foggie_load(dsname, box_trackfile, disk_relative=True)
    else:
        ds = yt.load(dsname)
    ds = yt.load(dsname)

    if bulk_velocity is not None:
        bulk_velocity = ds.arr(bulk_velocity, 'km/s')

    #add ion fields to dataset if not already there
    trident.add_ion_fields(ds, ions=line_list, ftype='gas')

    if other_fields is None:
        other_fields = default_ice_fields
    for line in line_list:
        ion_frac = ('gas', f"{ion_p(line)}_ion_fraction")
        other_fields.append(ion_frac)
    # add radius field to dataset
    ds.add_field(('gas', 'radius'),
             function=radius_function,
             units="code_length",
             take_log=False,
             validators=[yt.fields.api.ValidateParameter(['center'])])

    #collect sightlines
    start_points, end_points, impact_param = random_sightlines(dsname, center,
                                                 n_rays,
                                                 max_impact_param,
                                                 min_impact_param=min_impact_param,
                                                 length=length,
                                                 seed=seed)

    impact_param = ds.arr(impact_param, 'code_length').in_units('kpc').value
    np.save(f"{out_dir}/impact_parameter.npy", impact_param)

    #construct rays
    construct_rays(ds, start_points, end_points,
                   center=center, bulk_velocity=bulk_velocity,
                   line_list=line_list,
                   other_fields=other_fields,
                   out_dir=out_dir,
                   parallel=parallel)




if __name__ == '__main__':
    #setup conditions
    line_list = ['H I','H II','Si II', 'Si III', 'Si IV', 'C II', 'C IV', 'O VI', 'Ne VIII', 'Mg X']
    if len(argv) == 7:
        filename = argv[1]
        num_rays=int(argv[2])
        ray_length=int(argv[3])
        min_impact= int(argv[4])
        max_impact=int(argv[5])
        out_dir = argv[6]
    else:
        raise RuntimeError("Takes in 5 Arguments. Dataset_filename num_rays ray_lenght max_impact_param out_directory")

    my_seed = 2020 + 16*int(filename[-2:]) # this way each dataset has its own seed
    print(f"My seed is: {my_seed}")
    center, n_vec, rshift, bv = find_center(filename)
    random_rays(filename,
                center,
                num_rays,
                max_impact,
                min_impact_param=min_impact,
                bulk_velocity=bv,
                line_list=line_list,
                length=ray_length,
                out_dir=out_dir,
                seed=my_seed)
