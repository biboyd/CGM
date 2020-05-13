import matplotlib as mpl
mpl.use('Agg')
import yt
import trident
import numpy as np
from spectacle.fitting import LineFinder1D
from sys import argv, path
from os import remove, listdir, makedirs
import errno
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator
from mpl_toolkits.axes_grid1 import AxesGrid
from numpy.linalg import norm
import astropy.units  as u

path.insert(0, "/mnt/home/boydbre1/Repo")
from CGM.general_utils.filter_definitions import ion_p_num, default_units_dict, default_limits_dict
from CGM.general_utils.center_finder import find_center
from CGM.absorber_extraction_class.absorber_extractor import absorber_extractor

class absorber_plotter(absorber_extractor):
    """
    Create's plot to easily see where absorbers are found along the light ray
    both directly and through resulting spectra. Uses absorber extractor as base
    class.
    """

    def __init__(self,
                ds_filename,
                ray_filename,
                ion_name='H I',
                cut_region_filters=None,
                slice_field=None,
                absorber_fields=[],
                north_vector=[0, 0, 1],
                center_gal = None,
                wavelength_center=None,
                wavelength_width = 30,
                velocity_width = 3000,
                wavelength_res = 0.1,
                velocity_res = 10,
                redshift = 0,
                bulk_velocity=None,
                use_spectacle=False,
                plot_spectacle=False,
                spectacle_defaults=None,
                plot_ice=False,
                cloud_min=None,
                spectacle_res=None,
                frac=0.8,
                num_dense_min=None,
                num_dense_max=None,
                markers=True,
                mark_plot_args=None,
                figure=None):
        """
        init file names and ion name

        Parameters:
        ds_filename : Path/name of the enzo dataset to be loaded
        ray_filename : Path/name of the hdf5 ray file to be loaded
        ion_name :string: Name of the ion to plot in number density plot
        cut_region_filters : list of str: a list of filters defined by the way you use Cut Regions in YT
        slice_field :string: Field to plot in slice plot. defaults to ion_name's number density
        absorber_fields :list of strings: Additional ions to include in plots/Spectra, enter as list
        north_vector :array type: vector used to fix the orientation of the slice plot defaults to z-axis
        center_gal :array type: center of galaxy in code_length. if None, then defaults to domain_center
        wavelength_center :float: Wavelength to center spectrum plot on. defaults to the stringest
                        known spectral line of ion_name. in units of Angstrom
        wavelength_width :float: sets the wavelength range of the spectrum plot. defaults
                        to 300 Angstroms
        velocity_width :float: sets the velocity range in spectrum plot in units of km/s
        wavelegnth_res :float: width of wavelength bins in spectrum plot. default 0.1 Angstrom
        velocity_res :float: width of velocity bins in spectrum plot. default 10 km/s
        redshift :float: redshift of galaxy's motion. adjusts velocity plot calculation.
        bulk_velocity : array type : bulk velocity of the galaxy in km/s
        use_spectacle : bool: Choose whether to use spectacle fit to compute col dense
        spectacle_res : double : Set minimum resolution that spectacle will attempt
                                 to fit lines to. If None, default to velocity_res
        markers :bool: whether to include markers on light ray and number density plot
        mark_plot_args : dict : set the property of markers if they are to be plotted.
                        optional settings are:
                        marker_spacing : determines how far apart markers are in kpc
                        marker_shape : shape of marker see matplotlib for notation
                        marker_cmap : colormap used to differentiate markers
                        any other property that can be passer to matplotlib scatter
        ###NOTE### ion names should be in notaion:
              Element symbol *space* roman numeral of ion level (i.e. "H I", "O VI")
        figure :matplotlib figure: where the multi_plot will be plotted. creates one if
                        none is specified.
        """
        #set file names and ion name
        self.ds_filename = ds_filename
        self.ray_filename = ray_filename
        self.ion_name = ion_name

        self.cut_region_filters = cut_region_filters
        self.frac = frac

        #add ion name to list of all ions to be plotted
        self.ion_list = [ion_name] + absorber_fields

        #set a value for slice
        self.slice = None
        self.north_vector = north_vector
        self.center_gal= center_gal

        #open up the dataset and ray files
        self.ds = yt.load(self.ds_filename)
        self.load_ray(self.ray_filename)


        #set slice field to ion name if no field is specified
        if (slice_field is None):
            self.slice_field = ion_p_num(self.ion_name)
        else:
            self.slice_field = slice_field

        # set bulk velocity
        if bulk_velocity is None:
            self.bulk_velocity = None
        else:
            ray_b, ray_e, ray_l, ray_u = self.ray_position_prop()
            self.bulk_velocity = np.dot(ray_u, bulk_velocity)
            self.bulk_velocity = self.ds.quan(self.bulk_velocity, 'km/s')
        self.redshift = redshift

        # whether to use/plot these methods
        self.plot_ice = plot_ice
        self.use_spectacle = use_spectacle
        self.plot_spectacle = plot_spectacle

        if cloud_min is None:
            min_defaults = {'H I': 12.5, 'Si II': 11, 'Si IV': 12,
                            'C IV':13, 'O VI':13}
            if self.ion_name in min_defaults.keys():
                self.cloud_min = min_defaults[self.ion_name]
            else:
                self.cloud_min=13
        else:
            self.cloud_min = cloud_min

        # define defaults for spectacle fit
        self.defaults_dict = {
            'bounds' :{
                'column_density' : (self.cloud_min-0.5, 23)
            },
            'fixed' : {
                'delta_lambda' : True,
                'column_density' : False
            }
        }

        #add user defined defaults
        if spectacle_defaults is not None:
            self.defaults_dict.update(spectacle_defaults)

        #parameters for trident
        self.wavelength_width = wavelength_width
        self.wavelegnth_res = wavelength_res
        self.velocity_width = velocity_width
        self.velocity_res = velocity_res

        #default spectacle resolution to velocity_res
        if spectacle_res is None:
            self.spectacle_res = velocity_res
        else:
            self.spectacle_res = spectacle_res

        #default set the wavelength center to one of the known spectral lines
        #for ion name. Use tridents line database to search for correct wavelength
        if wavelength_center is None:
            #open up tridents default line database
            lbd = trident.LineDatabase('lines.txt')
            #find all lines that match ion
            lines = lbd.parse_subset(subsets= [self.ion_name])
            #take one with largest f_value
            f_val = 0
            for line in lines:
                if line.f_value >= f_val:
                    f_val = line.f_value
                    self.wavelength_center = line.wavelength
        else:
            self.wavelength_center = wavelength_center

        #open up a figure if none specified
        if figure is None:
            self.fig = plt.figure(figsize=(10, 10))
        else:
            self.fig = figure


        #set marker plot properties
        self.markers = markers
        if markers:
            self.mark_kwargs = {'alpha' : 0.45,
                                's' : 100,
                                'edgecolors' : 'black',
                                'linewidth' : 3,
                                'spacing' :50,
                                'marker_cmap' : 'viridis',
                                'marker_shape' :'s'}
            if mark_plot_args != None:
                self.mark_kwargs.update(mark_plot_args)

            self.marker_spacing = self.mark_kwargs.pop('spacing')
            self.marker_cmap = self.mark_kwargs.pop('marker_cmap')
            self.marker_shape = self.mark_kwargs.pop('marker_shape')
        self.mark_dist_arr = None

        #optionally set min/max value for number density plot
        self.num_dense_min = num_dense_min
        self.num_dense_max = num_dense_max



    def add_annotations(self, plot=True):
        """
        Adds ray and marker annotations to slice plot

        Parameters:
            plot : bool : Whether to annotate ray/markers to the slice plot or to just
            calculate the marker positions for placing on los_velocity plot
        """

        if plot:
            #annotate ray
            self.slice.annotate_ray(self.ray, arrow=True, plot_args={'alpha':0.5, 'color':'white', 'linewidth':2})

        if self.markers:
            #get ray positional properties
            ray_begin, ray_end, ray_length, ray_direction = self.ray_position_prop(units='kpc')
            #make marker every x kpc. skip start
            mark_dist = self.marker_spacing #kpc
            mark_dist_arr = np.arange(mark_dist, ray_length.value, mark_dist)
            self.mark_dist_arr = self.ds.arr(mark_dist_arr, 'kpc')

            #define colormap and scale
            mrk_cmap = plt.cm.get_cmap(self.marker_cmap)
            self.colorscale = np.linspace(0, 1, mark_dist_arr.size)

            if plot:
                #construct unit vec from ray
                for i in range(mark_dist_arr.size):
                    #calculate the position
                    mrk_pos = ray_begin + ray_direction * self.mark_dist_arr[i]

                    #choose correct color from cmap
                    mrk_kwargs = self.mark_kwargs.copy()
                    mrk_kwargs['color'] = mrk_cmap(self.colorscale[i])

                    self.slice.annotate_marker(mrk_pos, marker=self.marker_shape, plot_args=mrk_kwargs)

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
        #print("adding ion fields")

        #add ion fields to dataset if not already there
        trident.add_ion_fields(self.ds, ions=self.ion_list, ftype='gas')

        # runs way to slow, may add later
        if False: #self.cut_region_filters is not None:
            # parse for radial cuts
            rad_in, rad_out, cut_str = self.cgm_details
            cgm = self.ds.sphere(self.center_gal, (rad_out, 'kpc')) \
                  - self.ds.sphere(self.center_gal, (rad_in, 'kpc'))
            # cuts running too slow rn so just not including them
            data_source = cgm.cut_region(cut_str)
        else:
            data_source=None

        ray_begin, ray_end, ray_length, ray_unit = self.ray_position_prop(units='kpc')

        #construct vec orthogonal to ray/plane
        self.north_vector = self.ds.arr(self.north_vector, 'dimensionless')
        norm_vector = np.cross(ray_unit, self.north_vector)
        norm_vector = norm_vector/np.linalg.norm(norm_vector)

        #set center to domain_center unless specified
        if self.center_gal is None:
            self.center_gal = self.ds.domain_center
        else:
            self.center_gal = self.ds.arr(self.center_gal, 'code_length')

        #adjust center so that it is in the plane of ray and north_vector
        ray_center = (ray_begin + ray_end)/2
        ray_center = ray_center.in_units('code_length')
        center_dif = ray_center - self.center_gal
        scale = self.ds.quan(np.dot(center_dif, norm_vector), 'code_length')
        center = scale*norm_vector + self.center_gal

        #set width/height
        if width ==None and height==None:
            #default to length of ray
            wid_hght=ray_length
        elif width ==None and height != None:
            #width still defaults to length of ray
            wid_hght=((ray_length.to_value(), 'kpc'), (height, 'kpc'))
        elif width != None and height ==None:
            wid_hght= ((width, 'kpc'), (ray_length.to_value(), 'kpc'))
        else:
            wid_hght= ((width, 'kpc'), (height, 'kpc'))

        #Create slice along ray. keep slice pointed in north_Vec direction
        self.slice = yt.OffAxisSlicePlot(self.ds,
                          norm_vector,
                          self.slice_field,
                          center=center,
                          north_vector = self.north_vector,
                          width = wid_hght,
                          data_source=data_source)



        #set axes to kpc
        self.slice.set_axes_unit('kpc')

        #annotate plot
        self.add_annotations()

        # set color map
        self.slice.set_cmap(field=self.slice_field, cmap = cmap)

        # set background to bottom of color map
        self.slice.set_background_color(self.slice_field)

        return self.slice

    def plot_vel_space(self, ax=None, annotate_column_density=True):
        """
        Use trident to plot the absorption spectrum of the ray in velocity
        space. Compute column densities with spectacle fits.

        Parameters:
            ax : a matplotlib axis in which to draw the velocity plot
            annotate_column_density: bool : add a textbox reporting the calculated col
                    densities by each method.
        Returns:
            velocity and flux arrays created by spectrum generator
                units are km/s
        """
        # add wav center first so it is set as zero point velocity by trident
        wav = int( np.round(self.wavelength_center) )
        line = f"{self.ion_name} {wav}"
        ion_list = [line] + self.ion_list

        # calc doppler redshift due to bulk motion
        if self.bulk_velocity is None:
            z_tot=self.redshift
        else:
            c = yt.units.c
            beta = self.bulk_velocity/c
            z_dopp = (1 - beta)/np.sqrt(1 +beta**2) -1
            z_dopp = z_dopp.value
            z_tot = (1+self.redshift)*(1+z_dopp) - 1

        #set up spectra
        vel_min = -self.velocity_width/2
        vel_max = self.velocity_width/2
        spect_gen = trident.SpectrumGenerator(lambda_min=vel_min,
                                              lambda_max=vel_max,
                                              dlambda = self.velocity_res,
                                              bin_space="velocity")

        #generate spectra and return fields
        spect_gen.make_spectrum(self.data, lines=ion_list)
        flux = spect_gen.flux_field
        velocity = spect_gen.lambda_field.in_units('km/s')

        if ax is not None:
            #plot values for velocity plot
            ax.plot(velocity[:-1], flux[:-1])
            ax.set_ylim(0, 1.05)
            ax.set_xlim(vel_min, vel_max)
            ax.xaxis.set_minor_locator(AutoMinorLocator(2))
            ax.set_title(f"Rel. to line {self.wavelength_center:.1f} $\AA$", loc='right')
            ax.set_xlabel("Delta_v (km/s)")
            ax.set_ylabel("Flux")
            ax.grid(zorder=0, which='both')

            if self.use_spectacle:
                line_txt, line_models = self._get_vel_plot_annotations()
                box_props = dict(boxstyle='square', facecolor='white')

                if annotate_column_density:
                    #annotate plot with column densities
                    ax.text(0.8, 0.05, line_txt, transform=ax.transAxes, bbox = box_props)

                #annotate number of lines
                ax.text(0.9, 0.85, f"{self.num_spectacle} lines", transform=ax.transAxes, bbox = box_props)

                colors = ['tab:purple', 'tab:orange', 'tab:green']
                vel= np.linspace(vel_min, vel_max, 1000) *u.Unit('km/s')
                #plot individual column lines
                if line_models is not None:
                    for mod, color in zip(line_models, colors):
                        #plot centroids of largest lines
                        dv = mod.lines[0].delta_v.value
                        cd = mod.lines[0].column_density.value
                        ax.scatter(dv, 1, c=color, marker='v',zorder=5, label="logN={:04.1f}".format(cd))
                        #plott the largest lines
                        if self.plot_spectacle:
                            ax.step(vel, mod(vel), linestyle='--', color=color, alpha=0.75)
                    ax.legend(loc='lower left')


        return velocity, flux

    def plot_lambda_space(self, ax=None):
        """
        Use trident to plot the absorption spectrum of the ray. Plot in
        wavelegnth (lambda) space. Not formatted to be used in spectacle fitting

        Parameters:
            ax : a matplotlib axis in which to draw the spectra plot

        Returns:
            wavelength, flux arrays created by spectrum generator
                units are angstrom and flux is normalized to continuum=1
        """
        #set which ions to add to spectra
        ion_list = self.ion_list

        # calc doppler redshift due to bulk motion
        if self.bulk_velocity is None:
            z_tot = self.redshift
        else:
            c = yt.units.c
            beta = self.bulk_velocity/c
            z_dopp = (1 - beta)/np.sqrt(1 +beta**2) -1
            z_dopp = z_dopp.value
            #total redshift that takes in account bulk motion if specified
            z_tot = (1+self.redshift)*(1+z_dopp) -1

        #adjust wavelegnth_center for redshift
        rest_wavelength = self.wavelength_center
        wave_min = rest_wavelength - self.wavelength_width/2
        wave_max = rest_wavelength + self.wavelength_width/2

        #use wavelength_width to set the range
        spect_gen = trident.SpectrumGenerator(lambda_min=wave_min, lambda_max=wave_max, dlambda = self.wavelegnth_res)
        spect_gen.make_spectrum(self.data, lines=ion_list, observing_redshift=z_tot)


        #get fields from spectra and give correct units
        rest_wavelength = rest_wavelength*u.Unit('angstrom')
        wavelength = spect_gen.lambda_field * u.Unit('angstrom')
        flux = spect_gen.flux_field

        if ax is not None:
            #plot values for spectra
            ax.plot(wavelength[:-1], flux[:-1])
            ax.set_ylim(0, 1.05)
            ax.set_xlim(wave_min, wave_max)
            ax.xaxis.set_minor_locator(AutoMinorLocator(2))
            ax.set_title(f"Spectrum {self.ion_name}", loc='right')
            ax.set_xlabel("Wavelength $\AA$")
            ax.set_ylabel("Flux")
            ax.grid(zorder=0, which='both')

        return wavelength, flux

    def plot_num_density(self, ax_num_dense=None, ax_prop2=None, prop2_name='velocity_los', prop2_units=None, plot_kwargs={}):
        """
        Plots the number density at different lengths along the ray

        Parameters:
            ax : a matplotlib axis in which to draw the plot
        Returns:
            none
        """
        #get list of num density  los velocity and corresponding lengths
        num_density = self.data[ion_p_num(self.ion_name)]
        prop2 = self.data[prop2_name]

        prop2_lb = None
        prop2_ub = None

        #load defaults for prop2
        if prop2_units is None:

            #check if defaults for field
            if prop2_name in default_units_dict.keys():
                prop2_units = default_units_dict[prop2_name]
                prop2 = prop2.in_units(prop2_units)

                # set default bounds
                if prop2_name in default_limits_dict.keys():
                    prop2_lb, prop2_ub = default_limits_dict[prop2_name]

            else:
                # use default of trident (genarlly in cgs units)
                prop2_units = str(prop2.units)
        else:
            # convert to specified units
            prop2 = prop2.in_units(prop2_units)

        #add bulk velocity if wanted
        if self.bulk_velocity is not None and prop2_name == 'velocity_los':
            prop2 += self.bulk_velocity

        #get length data and define x limits
        l_list = self.data['l'].in_units('kpc')
        full_l = self.uncut_data['l'].in_units('kpc')
        pad = 0.1*full_l[-1]
        xlimits = [-pad, full_l[-1] + pad]

        # check if l_list is non-empty cuz something went wrong then.
        if l_list.size == 0:
            err_file = open("error_file.txt", 'a')
            err_file.write(f"{self.ray_filename} had an l_list that was of size zero")
            err_file.close()
            return 1

        if ax_num_dense is not None:
            #make num density plots
            ax_num_dense.plot(l_list, num_density, **plot_kwargs)
            ax_num_dense.set_title(f"Number Density of {self.ion_name} Along Ray", loc='right')
            ax_num_dense.set_xlabel("Length From Start of Ray $(kpc)$")
            ax_num_dense.set_ylabel("Number Density \n$(cm^{-3})$")
            ax_num_dense.set_yscale('log')
            ax_num_dense.grid(zorder=0)

            #chech if min/max num dense was called
            if (self.num_dense_min is None and self.num_dense_max is None):
                med = np.median(num_density)
                self.num_dense_min = med*0.01
                self.num_dense_max = med*1000

            #set axes limits
            ax_num_dense.set_ylim(self.num_dense_min, self.num_dense_max)
            ax_num_dense.set_xlim(xlimits[0], xlimits[1])
            #add minor tick marks
            ax_num_dense.xaxis.set_minor_locator(AutoMinorLocator(2))

            #check if should plot ice intervals
            if self.plot_ice:
                # run ice method if not already run
                if self.num_ice is None:
                    self.get_ice_absorbers()


                for i in range(self.num_ice):
                    b, e = self.ice_intervals[i]
                    curr_lcd = self.ice_table['col_dens'][i]

                    #plot interval
                    ax_num_dense.axvspan(l_list[b], l_list[e], alpha=0.5, edgecolor='black',facecolor='tab:grey')#vspan_cmap((curr_lcd-12)/11))

                    #plot on 2nd prop if axis exists
                    if ax_prop2 is not None:
                        ax_prop2.axvspan(l_list[b], l_list[e], alpha=0.5, edgecolor='black',facecolor='tab:grey')#vspan_cmap((curr_lcd-12)/11))

                #plot number of intervals found
                box_props = dict(boxstyle='square', facecolor='white')
                ax_num_dense.text(0.9, 0.85, f"{self.num_ice} feat.", transform=ax_num_dense.transAxes, bbox = box_props)

                #take three largest absorbers and sort by position
                max_indices = self.ice_table.argsort('col_dens')
                max_indices = max_indices[-3:]
                max_indices.sort()

                #plot markers from left to right
                colors=['black', 'magenta', 'yellow']
                for i,c in zip(max_indices, colors):
                    b, e = self.ice_intervals[i]
                    lcd = self.ice_table['col_dens'][i]
                    mid_point = (l_list[b]+l_list[e])/2

                    ax_num_dense.scatter(mid_point, 0.75*self.num_dense_max,
                                         marker='v',color=c, edgecolors='black',
                                         label=f"logN={lcd:.1f}", zorder=3)

                ax_num_dense.legend(loc='lower left', bbox_to_anchor=(-0.015, 0.95))

        #make second plot
        if ax_prop2 is not None:
            #plot zero mark if line of sight velocity
            if ax_prop2 == 'los_velocity':
                ax_prop2.hlines(0, l_list[0], l_list[-1], linestyles='dashed',alpha=0.25, zorder=1)

            ax_prop2.plot(l_list, prop2, **plot_kwargs)

            #set title and axis labels
            ax_prop2.set_title(f"{prop2_name} Along Ray", loc='right')
            ax_prop2.set_xlabel("Length From Start of Ray $(kpc)$")
            ax_prop2.set_ylabel(f"{prop2_name} $({prop2_units})$")

            #set limits
            ax_prop2.set_ylim(prop2_lb, prop2_ub)
            ax_prop2.set_xlim(xlimits[0], xlimits[1])

            #set minor ticks and grid lines
            ax_prop2.yaxis.set_minor_locator(AutoMinorLocator(2))
            ax_prop2.xaxis.set_minor_locator(AutoMinorLocator(2))
            ax_prop2.grid(zorder=0, which='major')
            ax_prop2.grid(zorder=0, which='minor', axis='y')

        #add appropriate markers to the plot
        if self.markers and ax_prop2 is not None:
            #check if marker distances have been defined
            if self.mark_dist_arr is None:
                self.add_annotations(plot=False)

            Vys = np.zeros_like(self.mark_dist_arr) - 500
            plot_markers = {}
            plot_markers.update(self.mark_kwargs)
            ax_prop2.scatter(self.mark_dist_arr.value, Vys,zorder=3, c=self.colorscale, marker=self.marker_shape, cmap=self.marker_cmap, **plot_markers)

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
            fig : matplotlib figure: figure multi_plot is drawn on
            axes : matplotlib axes: axes the three lower plots are drawn on
        """
        if (self.slice == None):
            #create the slicePlot using the field of the ion density
            self.create_slice(cmap = cmap)

        grid = AxesGrid(self.fig, (0.,0.,0.5,0.5),
                        nrows_ncols = (1, 1),
                        axes_pad = 0.5,
                        label_mode = "L",
                        share_all = False,
                        cbar_location="right",
                        cbar_mode="each",
                        cbar_size="3%",
                        cbar_pad="0%")

        #redraw slice plot onto figure
        plot = self.slice.plots[self.slice_field]
        plot.figure = self.fig
        plot.axes = grid[0].axes
        plot.cax = grid.cbar_axes[0]

        self.slice._setup_plots()

        #set up axes and draw other plots to them
        ax1 = self.fig.add_subplot(411)
        ax2 = self.fig.add_subplot(412)
        ax3 = self.fig.add_subplot(413)

        self.plot_num_density(ax_num_dense=ax1, ax_prop2=ax2)
        self.plot_vel_space(ax=ax3)

        axes= [ax1, ax2, ax3]
        #setup positioning for the plots underneath
        strt_pos = -0.255
        ax1.set_position( [0.0, strt_pos, 0.5, 0.15] )
        ax2.set_position( [0.0, strt_pos-0.16, 0.5, 0.15] )
        ax3.set_position( [0.0, strt_pos-0.4, 0.5, 0.15] )

        #set num dense and los vel to share axis
        ax1.set_xlabel("")
        ax2.set_title("", loc='right')
        ax1.get_shared_x_axes().join(ax1, ax2)
        ax1.set_xticklabels([])
        if (outfname != None):
            self.fig.savefig(outfname, bbox_inches='tight')

        return self.fig, axes

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
        plt.close(self.fig)

    def _get_vel_plot_annotations(self):
        """
        computes the column density along the given ray for a given ion species.
        This is done by using spectacle if use_spectacle is True. as well as
        by summing the product of the number density for a given length by that length.
        and the ICE method

        Parameters:
            none

        Returns:
            line_models : list spectacle models : Individual line models for the
                        3 largest absorbers found by spectacle
            line_text : string : a string of properly formatted col dense to
                        be added on to multi_plot
        """

        # run thw two methods if not already done
        if self.num_spectacle is None:
            # run spectacle method
            self.get_spectacle_absorbers()
        if self.num_ice is None:
            self.get_ice_absorbers()


        fit_label="Spect:"
        #check if no absorbers found
        if self.num_spectacle == 0:
            line_models = None
            fit_string = "{: <14s}{: >4s}\n".format(fit_label, '--')
        else:
            #get total column density and 3 largest lines
            tot_spect_cd, line_models = self._get_large_spectacle()
            fit_string = "{: <14s}{:04.1f}\n".format(fit_label, tot_spect_cd)

        #get sum from ICE method
        ice_label="ICE:"
        #check if no absorbers
        if self.num_ice == 0:
            ice_string = "{: <11s}{: >4s}\n".format(ice_label,'--')
        else:
            #find total column density for ICE method
            cd_sum=0
            for lcd in self.ice_table['col_dens']:
                cd_sum += 10**lcd

            log_cd_sum = np.log10(cd_sum)
            ice_string = "{: <11s}{:04.1f}\n".format(ice_label,log_cd_sum)

        #get total column density along ray
        ion_field = ion_p_num(self.ion_name)
        tot_ray_cd= np.sum( self.data[ion_field]*self.data['dl'] )
        log_tot_ray = np.log10(tot_ray_cd)
        total_string="{: <14s}{:04.1f}".format("full ray:", log_tot_ray)

        #combine strings to create "legend"
        line_text = "Tot Sums\n"+ice_string + fit_string + total_string

        return line_text, line_models

    def _get_large_spectacle(self):
        """
        Return the total column density found by spectacle and the 3 largest
        absorbers found by spectacle.
        """
        #compute total column density
        line_sum_cd = 0
        for cd in self.spectacle_table['col_dens']:
            line_sum_cd+= 10**cd
        log_tot_cd = np.log10(line_sum_cd)

        line_models = []
        indx_max = self.spectacle_table.argsort('col_dens')
        for indx in indx_max[-3:]:
            line = self.spectacle_model.lines[indx]
            line_models.append( self.spectacle_model.with_line(line, reset=True))

        #sort lines based on delta v
        line_models.sort(key=lambda mod: mod.lines[0].delta_v.value)

        return log_tot_cd, line_models
if __name__ == '__main__':
    data_set_fname = argv[1]
    ray_fname = argv[2]
    ion = argv[3]
    num=int(argv[4])
    absorbers = [ion] #['H I', 'O VI']
    center, nvec, rshift, bv = find_center(data_set_fname)
    cut_filters = ["((obj[('gas', 'radius')].in_units('kpc') > 10) & \
                   (obj[('gas', 'radius')].in_units('kpc') < 200)) & \
                   ((obj[('gas', 'temperature')].in_units('K') > 1.5e4) | \
                   (obj[('gas', 'density')].in_units('g/cm**3') < 2e-26))"]

    mp = absorber_plotter(data_set_fname, ray_fname, ion_name=ion, absorber_fields=absorbers,
                    center_gal=center, north_vector=nvec, bulk_velocity=None,plot_ice=True,use_spectacle=True,plot_spectacle=True,
                    redshift=rshift, cloud_min=12.5,wavelength_width = 30, cut_region_filters=cut_filters)
    makedirs("mp_frames", exist_ok=True)
    outfile = f"mp_frames/multi_plot_{ion[0]}_{num:02d}.png"
    mp.create_multi_plot(cmap='cividis',outfname=outfile)
