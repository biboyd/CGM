import yt
import trident
import numpy as np
from sys import argv
from os import remove, listdir, makedirs
import errno
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import AxesGrid
from numpy.linalg import norm

from scipy.constants import centi, kilo, parsec

class multi_plot():
    """
    Plots three images side by side for easy analysis. The images are:
    A slice of dataset along lightray's path.
    The number density of the given ion along that path.
    The artificial absorption spectra that would be observed.
    """
    #define conversion factor
    cm_to_kpc = centi/(parsec * kilo)

    def __init__(self,
                ds_filename,
                ray_filename,
                ion_name='H I',
                slice_field=None,
                absorber_fields=[],
                wavelength_center=None,
                wavelength_width = 300,
                resolution = 0.1,
                open_start=True,
                markers=True,
                figure=None):
        """
        init file names and ion name

        Parameters:
        ds_filename : Path/name of the enzo dataset to be loaded
        ray_filename : Path/name of the hdf5 ray file to be loaded

        ion_name : Name of the ion to plot in number density plot
        slice_field : Field to plot in slice plot. defaults to ion_name's number density
        absorber_fields : Additional ions to include in plots/Spectra, enter as list
        wavelength_center : Wavelength to center spectrum plot on. defaults to
                            a known spectral line of ion_name. in units of Angstrom
        wavelength_width : sets the wavelenth range of the spectrum plot. defaults
                            to 300 Angstroms
        resolution : width of wavelenth bins in spectrum plot. default 0.1 Angstrom
        markers : whether to include markers on light ray and number density plot
        figure : matplotlib figure where the multi_plot will be plotted. creates one if
                none is specified.
        open_start : option on whether to immediately open dataset and ray files. defaults to True.
        ###NOTE### ion names should be in notaion:
              Element symbol *space* roman numeral of ion level (i.e. "H I", "O VI")
        """
        #set file names and ion name
        self.ds_filename = ds_filename
        self.ray_filename = ray_filename
        self.ion_name = ion_name

        #add ion name to list of all ions to be plotted
        absorber_fields.append(ion_name)
        self.ion_list = absorber_fields

        #set a value for slice
        self.slice = None

        #set slice field to ion name if no field is specified
        if (slice_field == None):
            self.slice_field = self.ion_p_name() + "_number_density"
        else:
            self.slice_field = slice_field

        self.wavelength_width = wavelength_width
        self.resolution = resolution
        #default set the wavelenth center to one of the known spectral lines
        #for ion name. Use tridents line database to search for correct wavelenth
        if (wavelength_center == None):
            #open up tridents default line database
            lbd = trident.LineDatabase("lines.txt")
            #find all lines that match ion
            lines = lbd.parse_subset(subsets= [self.ion_name])
            #take first one and return its wavelenth
            self.wavelenth_center = lines[0].wavelength

        #open up a figure if none specified
        if (figure == None):
            self.fig = plt.figure(figsize=(10, 10))

        #open up the dataset and ray files or set their values to None
        if (open_start):
            self.ds = yt.load(self.ds_filename)
            self.ray = yt.load(self.ray_filename)
        else:
            self.ds = None
            self.ray = None

        self.markers = markers
        #optionally set min/max value for number density plot
        self.num_dense_min = None
        self.num_dense_max = None


    def open_files(self, open_ds=True, open_ray=True):
        """
        Opens dataset and ray files with yt

        Parameters:
            open_ds : bool operator. whether or not the dataset should be opened
            open_ray :bool operator. whether or not the ray should be opened

        Returns:
        ds : dataset object loaded into yt or None if open_ds = False
        ray : ray object loaded into yt or None if open_ray = False
        """
        #open ds if open_ds = True
        ds = yt.load(self.ds_filename) if open_ds else None

        #open ray file in its two forms if open_ray = True
        if (open_ray):
            ray = yt.load(self.ray_filename)

        else:
            ray = None


        return ds, ray

    def ion_p_name(self):
        """
        convert ion species name to yt style field convention
        ('H I' -> 'H_p0')
        Returns:
        outname : Name of the ion in the yt form
        """

        ######### Deprecated, no longer needed #########3
        # 'H I' is an exception just return H

        #if self.ion_name == 'H I':
        #    return 'H'

        #split up the words in ion species name
        ion_split = self.ion_name.split()

        #convert num from roman numeral. subtract one to follow convention
        num = trident.from_roman(ion_split[1])-1

        #combine all the names
        outname = ion_split[0] + '_p' + str(num)
        return outname

    def create_slice(self, cmap="magma", height=None, width=None):
        """
        Create a slice in the Dataset along the path of the ray.
        Choose to keep the Z direction maintained.

        Parameters:
        field: The yt field to plot for the slice
        cmap='magma' : the colormap to use for the slice

        Returns:
        slice : yt SlicePlot with ray annotated
        """

        #add ion fields to dataset if not already there
        trident.add_ion_fields(self.ds, ions=self.ion_list, ftype='gas')

        # get beginning and end of ray
        x = self.ray.all_data()['x']
        y = self.ray.all_data()['y']
        z = self.ray.all_data()['z']

        ray_begin = self.ds.arr([ x[0], y[0], z[0] ], 'cm')
        ray_end = self.ds.arr([ x[-1], y[-1], z[-1] ], 'cm')

        ray_begin = ray_begin.in_units('kpc')
        ray_end = ray_end.in_units('kpc')

        #construct vector pointing in ray's direction
        ray_vec = ray_end - ray_begin
        ray_length = self.ds.quan(norm(ray_vec.value), 'kpc')
        #construct vec orthogonal to ray
        norm_vector = [ray_vec[1], -1*ray_vec[0], 0]

        #get center of ray keep z at center
        center = self.ds.domain_center

        ray_center = (ray_begin + ray_end)/2
        ray_center[2] = center[2]

        #handle case where it is an on axis slice in the y plane
        #yt will ignore north_vector and place z-axis on horizontal axis
        if (norm_vector[0] == 0):
            # change yt coordinates so that z-axis is vertical
            self.ds.coordinates.x_axis[1] = 0
            self.ds.coordinates.x_axis['y'] = 0

            self.ds.coordinates.y_axis[1] = 2
            self.ds.coordinates.y_axis['y'] = 2

        #Create slice along ray. keep slice pointed in z-direction
        slice = yt.SlicePlot(self.ds,
                          norm_vector,
                          self.slice_field,
                          north_vector = [0, 0, 1],
                          center = center)

        #set width/height
        if width ==None and height==None:
            #default to length of ray
            slice.set_width(ray_length)
        elif width ==None and height != None:
            #width still defaults to length of ray
            slice.set_width(ray_length, (height, 'kpc') )
        elif width != None and height ==None:
            slice.set_width( (width, 'kpc'), ray_length )
        else:
            slice.set_width( (width, 'kpc'), (height, 'kpc') )

        #set axes to kpc
        slice.set_axes_unit('kpc')

        # add ray to slice
        slice.annotate_ray(self.ray, arrow=True)

        if self.markers:
            #make marker every x kpc. skip start
            mark_dist = 25 #kpc
            mark_dist_arr = np.arange(mark_dist, ray_length.value, mark_dist)
            self.mark_dist_arr = self.ds.arr(mark_dist_arr, 'kpc')

            #define colormap and scale
            mrk_cmap = plt.cm.get_cmap('viridis')
            self.colorscale = np.linspace(0, 1, mark_dist_arr.size)

            #construct unit vec from ray
            ray_direction = ray_vec/ray_length
            for i in range(mark_dist_arr.size):
                #calculate the position
                mrk_pos = ray_begin + ray_direction * self.mark_dist_arr[i]

                #choose corrct color from cmap
                mrk_kwargs = {'color': mrk_cmap(self.colorscale[i]),
                             'alpha' : 0.45,
                             's' : 100,
                             'edgecolors' : 'black',
                             'linewidth' : 3}

                slice.annotate_marker(mrk_pos, marker='s', plot_args=mrk_kwargs)

        # set y label to Z
        slice.set_ylabel("Z (kpc)")

        # set color map
        slice.set_cmap(field=self.slice_field, cmap = cmap)

        # set background to bottom of color map
        slice.set_background_color(self.slice_field)

        #assign slice
        self.slice = slice
        return slice

    def plot_spect(self, ax, fname=None):
        """
        Use trident to plot the absorption spectrum of the ray.
        currently defaults to using COS wavelength binning and range.
        Parameters:
            ax : a matplotlib axis in which to draw the plot
            fname=None : filename to save spectrum data
        Returns:
            none
        """
        #set max and min wavelength and resolution
        wave_min = self.wavelenth_center - self.wavelength_width/2
        wave_max = self.wavelenth_center + self.wavelength_width/2
        #generate spectrum defined by inputs
        spect_gen = trident.SpectrumGenerator(lambda_min=wave_min, lambda_max=wave_max, dlambda = self.resolution)
        spect_gen.make_spectrum(self.ray, lines=self.ion_list, output_file = fname)

        if fname != None:
            #save the spectrum to hdf5
            spect_gen.save_spectrum(fname)

        #get wavelength and flux in order to plot
        wavelength = spect_gen.lambda_field
        flux = spect_gen.flux_field

        #plot values
        ax.plot(wavelength, flux)
        ax.set_ylim(0, 1.05)
        ax.set_title(f"Spectrum {self.ion_name}")
        ax.set_xlabel("Wavelength (Angstrom)")
        ax.set_ylabel("Flux")

    def plot_num_density(self, ax):
        """
        Plots the number density at different lengths along the ray

        Parameters:
            ax : a matplotlib axis in which to draw the plot
        Returns:
            none
        """
        #get list of num density and corresponding lengths
        num_density = np.array(self.ray.all_data()[self.ion_p_name()+'_number_density'])
        dl_list = np.array(self.ray.all_data()['dl'])

        #convert list of dl's to list of lengths from begin of ray
        num_dls = len(dl_list)
        for i in range(1, num_dls):
            dl_list[i] += dl_list[i-1]

        # convert to kpc
        dl_list = dl_list*self.cm_to_kpc

        #make num density plots
        ax.plot(dl_list, num_density)
        ax.set_title(f"Number Density of {self.ion_name} Along Ray")
        ax.set_xlabel("Length From Start of Ray $(kpc)$")
        ax.set_ylabel("Number Density $(cm^{-3})$")
        ax.set_yscale('log')

        #chech if min/max num dense was called
        if (self.num_dense_min == None and self.num_dense_max == None):
            pass
        else:
            ax.set_ylim(self.num_dense_min, self.num_dense_max)

        #add appropriate markers to the plot
        if self.markers:
            ys = np.zeros_like(self.mark_dist_arr)
            ys += num_density.min()
            ax.scatter(self.mark_dist_arr.value, ys, c=self.colorscale, marker='s', cmap='viridis')

    def create_multi_plot(self, outfname=None, markers=True, cmap="magma"):
        """
        combines the slice plot, number density plot, and spectrum plot into
        one image.

        Parameters:
            outfname=None : the file name/path in which to save the file defaults
                              to being unsaved

            markers=True : boolean. adds markers to slice plot and number density
                            to aid analysis between those plots.

            cmap='magma' :     the color map to use for the slice plot

        Returns:
            none
        """
        if (self.slice == None):
            #create the slicePlot using the field of the ion density
            self.create_slice(cmap = cmap)

        grid = AxesGrid(self.fig, (0.075,0.075,0.85,0.85),
                        nrows_ncols = (1, 1),
                        axes_pad = 1.0,
                        label_mode = "L",
                        share_all = True,
                        cbar_location="right",
                        cbar_mode="each",
                        cbar_size="3%",
                        cbar_pad="0%")


        plot = self.slice.plots[self.slice_field]
        plot.figure = self.fig
        plot.axes = grid[0].axes
        plot.cax = grid.cbar_axes[0]

        self.slice._setup_plots()

        ax2 = self.fig.add_subplot(312)
        self.plot_num_density(ax2)

        ax3 = self.fig.add_subplot(313)
        self.plot_spect(ax3)

        ax2.set_position([1.1, 0.52, 1, 0.42])
        ax3.set_position([1.1, 0, 1, 0.42])


        if (outfname != None):
            self.fig.savefig(outfname, bbox_inches='tight')


    def zoom(self, factor):
        """
        Zoom into the slice by specified factor

        Parameters:
            factor : factor by which to zoom in using yt's zoom mehtod

        Returns:
            none
        """

        self.slice.zoom(factor)

    def close(self):
        """
        close all opened files
        """

        self.ds.close()
        self.ray.close()

    def compute_col_density(self):
        """
        computes the column density along the given ray for a given ion species. This is done
        by summing the product of the number density for a given length by that length.

        Parameters:

        """
        if (self.ray == None):
            self.ray = yt.load(self.ray_filename)

        #get list of num density and corresponding length
        num_density = np.array(self.ray.all_data()[self.ion_p_name()+'_number_density'])
        dl_array = np.array(self.ray.all_data()['dl'])

        #multiply num density by its dl and sum up to get column density
        col_density = np.sum( num_density*dl_array )

        return col_density

class movie_multi_plot(multi_plot):

    def __init__(self,
            ds_filename,
            ray_dir,
            ion_name='H I',
            slice_field=None,
            absorber_fields=[],
            wavelength_center=None,
            wavelength_width = 300,
            resolution = 0.1,
            out_dir="./frames"):
        """
        Parameters:
        ds_filename : Path/name of the enzo dataset to be loaded
        ray_dir : Path/name of the directory of numbered hdf5 ray files

        ion_name : Name of the ion to plot in number density plot
        slice_field : Field to plot in slice plot. defaults to ion_name's number density
        absorber_fields : Additional ions to include in plots/Spectra, enter as list
        wavelength_center : Wavelength to center spectrum plot on. defaults to
                            a known spectral line of ion_name. in units of Angstrom
        wavelength_width : sets the wavelenth range of the spectrum plot. defaults
                            to 300 Angstroms
        resolution : width of wavelenth bins in spectrum plot. default 0.1 Angstrom
        ###NOTE### ion names should be in notaion:
              Element symbol *space* roman numeral of ion level (i.e. "H I", "O VI")

        out_dir : Directory in which to store the movie frames
        """

        self.ds_filename = ds_filename

        #create directory if doesn't exist
        try:
            makedirs(out_dir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        #collect only ray files in ray_dir
        ray_files=[]
        for f in listdir(ray_dir):
            if (f[-3:] == ".h5"):
                ray_files.append(f)

        #sort the rays and assign
        self.ray_files = sorted(ray_files)
        self.ray_dir = ray_dir

        self.ion_name = ion_name
        #add ion name to list of all ions to be plotted
        absorber_fields.append(ion_name)
        self.ion_list = absorber_fields

        #set a value for slice
        self.slice =None

        #set slice field to ion name if no field is specified
        if (slice_field == None):
            self.slice_field = self.ion_p_name() + "_number_density"
        else:
            self.slice_field = slice_field

        self.wavelength_width = wavelength_width
        self.resolution = resolution
        #default set the wavelenth center to one of the known spectral lines
        #for ion name. Use tridents line database to search for correct wavelenth
        if (wavelength_center == None):
            #open up tridents default line database
            lbd = trident.LineDatabase("lines.txt")
            #find all lines that match ion
            lines = lbd.parse_subset(subsets= [self.ion_name])
            #take first one and return its wavelenth
            self.wavelenth_center = lines[0].wavelength


        self.out_dir = out_dir

    def create_movie(self, slice_height=None, slice_width=None, cmap="magma"):
        """
        creates a movie by combining all the plots made from the ray in ray_dir

        Parameters:
            slice_height : The vertical height of the slice plot in kpc. Defaults to lenght of ray
            slice_width : The vertical height of the slice plot in kpc. Defaults to length of ray
            cmap="magma" : the colormap with which to use for the slice plot
        """
        #open up dataset
        self.ds = yt.load(self.ds_filename)
        #create fig to plot on
        self.fig = plt.figure(figsize=(10, 10))

        #calculate the proper yscale for number density plot
        tot_median=0.

        #get middle ray to represent scale
        num_rays = len(self.ray_files)
        middle_ray_file = self.ray_files[ int(num_rays/2) ]
        mid_ray= yt.load( f"{self.ray_dir}/{middle_ray_file}" )

        #get median num density
        num_density = np.array(mid_ray.all_data()[ f"{self.ion_p_name()}_number_density" ])
        med = np.median(num_density)


        #construct the first/template slice using middle ray
        self.ray = mid_ray
        self.create_slice(width=slice_width, height=slice_height)
        mid_ray.close()

        #estimate min max values to plot
        self.num_dense_min = 0.01*med
        self.num_dense_max = 1000*med

        #set padding for filenames
        pad = np.floor( np.log10(num_rays) )
        pad = int(pad) + 2
        for i in range(num_rays):

            #assign the current ray filename
            ray_filename = f"{self.ray_dir}/{self.ray_files[i]}"
            #open the current ray file
            self.ray = yt.load(ray_filename)

            #annotate slice with ray and title
            self.slice.annotate_clear()
            self.slice.annotate_ray(self.ray, arrow=True)
            self.slice.annotate_title(f"ray {i:0{pad}d}")

            #create multi_plot using slice and current ray plots
            self.create_multi_plot(outfname = f"{self.out_dir}/mp{i:0{pad}d}", cmap=cmap)

            #close ray files and clear figure
            self.ray.close()

            self.fig.clear()

def construct_rays( dataset,
                    line_list,
                    length=200,
                    n_rays=100,
                    direction='z',
                    angle=0,
                    dist_from_center=200,
                    out_dir='./rays',
                    DEBUG=False):
    """
    Constructs a number of light rays to "scan" a galactic data set using trident

    Parameters:
        dataset: enzo dataset on which to construct the rays
        line_list: list of ions to include in rays
        length: the length of the rays in kpc
        n_rays: the number of rays to construct
        direction: the coordinate direction in which to "scan" the galaxy
        angle: The azimuthal angle around the direction. in degrees
        dist_from_center: range to construct rays. in kpc from center of galaxy
        out_dir: directory in which to save the rays

    Returns:
        none
    """
    if DEBUG:
        print(trident.__version__)
    ds = yt.load(dataset)
    #add ion fields to dataset if not already there
    trident.add_ion_fields(ds, ions=line_list, ftype='gas')

    #create directory if doesn't exist
    try:
        makedirs(out_dir)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

    #convert lengths to code_length and angle to radians
    length = ds.quan(length, 'kpc').in_units('code_length')
    dist_from_center = ds.quan(dist_from_center, 'kpc').in_units('code_length')
    angle = np.deg2rad(angle)

    #get right indexing for direction
    if (direction == 'x'):
        dir_index=0
        coord1_index=1
        coord2_index=2
    elif (direction == 'y'):
        dir_index=1
        coord1_index=2
        coord2_index=0
    elif (direction == 'z'):
        dir_index=2
        coord1_index=0
        coord2_index=1
    else:
        raise RuntimeError("direction must be 'x', 'y', or 'z'")

    #calculate the changing coordinate
    begin = ds.domain_center[dir_index] + dist_from_center
    end = ds.domain_center[dir_index] - dist_from_center
    direct_coord = np.linspace(begin, end, n_rays)

    #compute ray length in the coordinate directions
    len_coord1 = length/2* np.cos(angle)
    len_coord2 = length/2* np.sin(angle)

    #calc beginning and ending of ray for constant coordinates
    coord1_begin = ds.domain_center[coord1_index] - len_coord1
    coord1_end = ds.domain_center[coord1_index] + len_coord1

    coord2_begin = ds.domain_center[coord2_index] - len_coord2
    coord2_end = ds.domain_center[coord2_index] + len_coord2

    #empty ray coordinates to be filled
    ray_begin = ds.arr(np.zeros(3), "code_length")
    ray_end = ds.arr(np.zeros(3), "code_length")

    #set padding for filenames
    pad = np.floor( np.log10(n_rays) )
    pad = int(pad) + 2

    for i in range(n_rays):
        #set beginning ray
        ray_begin[dir_index] = direct_coord[i]
        ray_begin[coord1_index] = coord1_begin
        ray_begin[coord2_index] = coord2_begin

        #set ending ray
        ray_end[dir_index] = direct_coord[i]
        ray_end[coord1_index] = coord1_end
        ray_end[coord2_index] = coord2_end

        #construct ray
        trident.make_simple_ray(ds,
                                ray_begin,
                                ray_end,
                                lines=line_list,
                                data_filename= f"{out_dir}/ray{i:0{pad}d}.h5")

if __name__ == '__main__':
    data_set_fname = argv[1]
    ray_fname = argv[2]
    ion = argv[3]
    absorbers = [ion] #['H I', 'O VI']

    mp = multi_plot(data_set_fname, ray_fname, ion_name=ion, absorber_fields=absorbers, wavelength_width = 100)

    outfile = "multi_plot_" + ion[0] +".png"
    mp.create_multi_plot(outfname=outfile)
