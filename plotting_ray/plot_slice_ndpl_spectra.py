import yt
import trident as tri
import numpy as np
from sys import argv
import h5py
from os import remove
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import AxesGrid
from numpy.linalg import norm

from scipy.constants import centi, kilo, parsec


# =================== #
#
#
# =================== #

def create_slice(ds, ray, ray_h5file, field='density'):
    """
    Create a slice along path of ray. Orient it so that the Z direction is maintained
    """

    # get beginning and end of ray
    x = ray_h5file['grid']['x']
    y = ray_h5file['grid']['y']
    z = ray_h5file['grid']['z']

    ray_begin = np.array([ x[0], y[0], z[0] ])
    ray_end = np.array([ x[-1], y[-1], z[-1] ])

    #construct vector pointing in ray's direction
    ray_vec = ray_end - ray_begin

    #construct vec orthogonal to ray
    norm_vector = [ray_vec[1], -1*ray_vec[0], 0]

    #get center of ray keep z at center
    center = ds.domain_center

    ray_center = (ray_begin + ray_end)/2
    ray_center[2] = center[2]

    #Create slice along ray. keep slice pointed in z-direction
    slice = yt.SlicePlot(ds,
                      norm_vector,
                      field,
                      north_vector = [0, 0, 1],
                      center = center,
                      width=(norm(ray_vec), "cm"),
                      axes_unit="kpc")
    # add ray to slice
    slice.annotate_ray(ray)

    # set y label to Z
    slice.set_ylabel("Z (kpc)")

    # set color map
    slice.set_cmap('density', 'dusk')
    return slice


def plot_spect(ray, ion_name, ax, fname=".temp.h5"):
    """

    """
    line_list = [ion_name]
    #generate spectrum defined by inputs
    spect_gen = tri.SpectrumGenerator('COS')
    spect_gen.make_spectrum(ray, lines=line_list, output_file = fname)

    #save the spectrum to hdf5
    spect_gen.save_spectrum(fname)

    #open saved file to get wavelength and flux
    spect_h5 = h5py.File(fname)

    wavelength = np.array(spect_h5['wavelength'])
    flux = np.array(spect_h5['flux'])

    #close and delete temp file
    spect_h5.close()
    remove(fname)

    #plot values
    ax.plot(wavelength, flux)
    ax.set_title("Spectra {} ".format(ion_name))
    ax.set_xlabel("Wavelength (Angstrom)")
    ax.set_ylabel("Flux")

def plot_num_density(ray_h5file, ion_name, ax):
    """

    """
    #get list of num density and corresponding lengths
    num_density = np.array(ray_h5file['grid'][ion_p_name(ion_name)+'_number_density'])
    dl_list = np.array(ray_h5file['grid']['dl'])

    #convert list of dl's to list of lengths from begin of ray
    num_dls = len(dl_list)
    for i in range(1, num_dls):
        dl_list[i] += dl_list[i-1]

    # convert to kpc
    dl_list = dl_list*centi/(parsec * kilo)

    #shift to set center at zero
    dl_list -= dl_list[-1]/2
    #make y log
    #make num density plots
    ax.plot(dl_list, num_density)
    ax.set_title("Number Density of {} Along Ray".format(ion_name))
    ax.set_xlabel("Length From Start of Ray $(kpc)$")
    ax.set_ylabel("Number Density $(cm^{-3})$")
    ax.set_yscale('log')


def compute_col_density(ray_h5file, ion_name, outfname="combined_plot"):
    """

    """
    #get list of num density and corresponding length
    num_density = np.array(ray_h5file['grid'][ion_p_name(ion_name)+'_number_density'])
    dl_array = np.array(ray_h5file['grid']['dl'])

    #multiply num density by its dl and sum up to get column density
    col_density = np.sum( num_density*dl_array )

    return col_density

def plot_all(ds_file_name, ray_file_name, ion_name, outfname, field = 'density'):
    ds, ray, rayh5 = open_files(data_set_fname, ray_fname)

    fig = plt.figure(figsize=(10, 10))


    grid = AxesGrid(fig, (0.075,0.075,0.85,0.85),
                    nrows_ncols = (1, 1),
                    axes_pad = 1.0,
                    label_mode = "L",
                    share_all = True,
                    cbar_location="right",
                    cbar_mode="each",
                    cbar_size="3%",
                    cbar_pad="0%")

    slice = create_slice(ds, ray, rayh5, field)

    plot = slice.plots[field]
    plot.figure = fig
    plot.axes = grid[0].axes
    plot.cax = grid.cbar_axes[0]

    slice._setup_plots()

    ax2 = fig.add_subplot(312)
    plot_num_density(rayh5, ion_name, ax2)

    ax3 = fig.add_subplot(313)
    plot_spect(ray, ion_name, ax3)

    ax2.set_position([1.1, 0.52, 1, 0.42])
    ax3.set_position([1.1, 0, 1, 0.42])

    fig.savefig(outfname, bbox_inches='tight')

def ion_p_name(ion_name):
    """
    convert ion species name from trident style to one that
    can be used with h5 files
    """

    # 'H I' is an exception just return H
    if ion_name == 'H I':
        return 'H'

    #split up the words in ion species name
    ion_split = ion_name.split()

    #convert num from roman numeral. subtract run b/c h5
    num = tri.from_roman(ion_name[1])-1

    #combine all the names
    outname = ion_split[0] + '_p' + num
    return outname

def open_files(ds_file_name, ray_file_name):
    ds = yt.load(ds_file_name)
    ray = yt.load(ray_file_name)
    ray_h5file = h5py.File(ray_file_name)

    return ds, ray, ray_h5file

if __name__ == '__main__':
    data_set_fname = argv[1]
    ray_fname = argv[2]
    #ds, ray, rayh5 = open_files(data_set_fname, ray_fname)
    ion = 'H I'

    """plot_spect(ray, "spectra.txt")
    frb = plot_slice(ds, ray, rayh5)
    plot_num_density(rayh5, ion)
    print(compute_col_density(rayh5, ion))"""

    plot_all(data_set_fname, ray_fname, ion, "combined_plot.png")