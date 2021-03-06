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
from astropy.table import QTable

from CGM.general_utils.filter_definitions import ion_p_num, default_ice_fields, default_units_dict, default_cloud_dict

path.insert(0,"/mnt/home/boydbre1/Repo/foggie")
from foggie.utils.foggie_load import foggie_load

class absorber_extractor():
    """
    Extracts absorbers from a trident lightray for a given ion species. Does This
    through two methods, by using ICE (Iterative Cloud Extraction) and
    by fitting a synthetic spectra made by trident. Fit is done using spectacle

    Parameters
    --------------

    ds_filename: string
        Path/name of the enzo dataset to be loaded

    ray_filename: string
        Path/name of the hdf5 ray file to be loaded

    ion_name: string, optional
        Name of the ion to plot in number density plot
        Default: "H I"

    cut_region_filters: list of strings, optional
        a list of filters defined by the way you use Cut Regions in YT
        Default: None

    wavelegnth_center: float, optional
        The specific absorption line to look at (in unit Angstrom). None
        defaults to strongest absorption line for specified ion
        (using tridents ion table).
        Default: None

    velocity_res: float, optional
        width of velocity bins in spectrum plot (in km/s).
        Default: 10

    redshift: float, optional
        redshift of galaxy's motion. adjusts bulk velocity plot calculations.
        Default: 0.

    bulk_velocity: array type, optional
        bulk velocity of the galaxy (in km/s)
        Default: None

    spectacle_res: float, optional
        Set minimum resolution that spectacle will attempt to fit lines to.
        (in km/s) If None, default to value of velocity_res
        Default: None

    spectacle_defaults: dict, optional
        Dictionary passed to spectacle defining default parameters/ranges
        when fitting absorption lines
        Deafult: None

    absorber_min: float, optional
        Minimum Log Column Density that will be used to define an absorber.
        If None, defaults to either default for specific ion or 13
        Default: None

    frac: float, optional
        Parameter defining what fraction of the number density is being
        accounted for in each iteration of the ICE method. Must be a number
        between 0 and 1.
        Default: 0.8

    """

    def __init__(self, ds_filename, ray_filename,
                ion_name='H I', cut_region_filters=None,
                use_foggie_load=True,
                wavelength_center=None, velocity_res = 10,
                redshift = 0, bulk_velocity=None,
                spectacle_defaults=None, spectacle_res=None,
                absorber_min=None, frac=0.8):



        #set file names and ion name
        self.ds_filename = ds_filename
        self.ray_filename = ray_filename
        self.ion_name = ion_name
        self.cut_region_filters = cut_region_filters
        self.frac = frac

        #add ion name to list of all ions to be plotted
        self.ion_list = [ion_name]

        #open up the dataset and ray files
        if use_foggie_load:
            box_trackfile = '/mnt/home/boydbre1/data/track_files/halo_track_200kpc_nref10' #might want to make more flexible
            hcv_file='/mnt/home/boydbre1/Repo/foggie/foggie/halo_infos/008508/nref11c_nref9f/halo_c_v'
            self.ds, reg_foggie = foggie_load(self.ds_filename, box_trackfile,
                                              halo_c_v_name=hcv_file, disk_relative=True)
        else:
            self.ds = yt.load(self.ds_filename)
        self.load_ray(self.ray_filename)

        # set bulk velocity
        if bulk_velocity is None:
            self.bulk_velocity = None
        else:
            ray_b, ray_e, ray_l, ray_u = self.ray_position_prop()
            self.bulk_velocity = np.dot(ray_u, bulk_velocity)
            self.bulk_velocity = self.ds.quan(self.bulk_velocity, 'km/s')

        if absorber_min is None:
            if self.ion_name in default_cloud_dict.keys():
                self.absorber_min = default_cloud_dict[self.ion_name]
            else:
                self.absorber_min=13
        else:
            self.absorber_min = absorber_min

        self.defaults_dict = {
            'bounds' :{
                'column_density' : (self.absorber_min-0.5, 23)
            },
            'fixed' : {
                'delta_lambda' : True,
                'column_density' : False
            }
        }

        #add user defined defaults
        if spectacle_defaults is not None:
            self.defaults_dict.update(spectacle_defaults)

        self.redshift = redshift
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

    def load_ray(self, new_ray):
        """
        loads a new ray into the multi_plot class. (same dataset)

        Parameters
        -----------
        new_ray :str or yt.ray
            either filename to rayfile or a trident ray that's already opened

        Returns
        ---------

        """
        #reset absorber extraction variables
        # variables to store raw info from the different methods
        self.spectacle_model=None
        self.ice_intervals=None

        # to store absorber feature table
        self.ice_table=None
        self.spectacle_table=None

        #store number of features found
        self.num_ice = None
        self.num_spectacle = None

        #check if str else assume is ray
        if isinstance(new_ray, str):
            self.ray_filename=new_ray
            self.ray = yt.load(new_ray)
        else:
            self.ray = new_ray
            self.ray_filename=new_ray.filename_template

        #save uncut data. define center
        self.uncut_data = self.ray.all_data()

        #apply cut region if specified
        if self.cut_region_filters is None:
            self.data = self.uncut_data
        else:
            curr_data = self.uncut_data
            #iteratively apply filters
            for filter in self.cut_region_filters:
                curr_data = curr_data.cut_region(filter)

            self.data = curr_data

        # Check if ray is empty due to cuts
        if self.data['l'].size == 0:
            print(f'light ray {self.ray} is empty')

    def ray_position_prop(self, units='code_length'):
        """
        returns positional/directional properties of the ray so that it can be used like a vector

        Parameters:
            units : YT defined units to return arrays in. defaults to 'code length'
        Returns:
            ray_begin : (YT arr): the starting coordinates of ray
            ray_end : (YT arr): the ending coordinates of the ray
            ray_length :(YT arr): the length of the ray
            ray_unit :(YT arr): unit vector showing direction of the ray
        """
        #get start and end points of ray. convert to defined units
        #print(self.ray)
        ray_begin = self.ray.light_ray_solution[0]['start']
        ray_end = self.ray.light_ray_solution[0]['end']

        ray_begin = ray_begin.in_units(units)
        ray_end = ray_end.in_units(units)

        #construct vector pointing in ray's direction
        ray_vec = ray_end - ray_begin
        ray_length = self.ds.quan(norm(ray_vec.value), units)

        #normalize vector to unit length
        ray_unit = ray_vec/ray_length

        return ray_begin, ray_end, ray_length, ray_unit

    def close(self):
        """
        close all opened files, dataset, ray
        """

        self.ds.close()
        self.ray.close()

    def get_ice_absorbers(self, fields=None, user_unit_dict=None):
        """
        Use the ICE method to extract absorbers and then find features of
        absorbers. Default outputs column density and central velocity of the
        absorption line (delta_v) as well as default_ice_fields which are density
        weighted averages of yt fields (metallicity, temperature, etc.). All in
        a astropy QTable.

        Parameters
        ----------

        fields : list, optional
            list of yt fields to extract averages of for the absorbers.
            None defaults to default_ice_fields in general_utils.filter_definitions.
            Defalut: None

        user_unit_dict : dict, optional
            dictionary of fields and corresponding units to use for each field.
            None defaults to default_units_dict in general_utils.filter_definitions.
            Default: None

        Returns
        ---------

        stats_table : astropy.table.QTable
            QTable of all the absorbers and their corresponding features.
        """
        # get absorber locations
        self.ice_intervals = self.run_ice()
        self.num_ice = len(self.ice_intervals)
        if fields is None:
            # set default fields to extract
            fields = default_ice_fields

        #use default unit dict
        if user_unit_dict is None:
            unit_dict = default_units_dict
        #update default dict with specified units
        else:
            unit_dict = default_units_dict
            unit_dict.update(user_unit_dict)

        # line information for absorbers
        line_info = [('name', 'S8'),
                     ('wave', np.float64),
                     ('redshift', np.float64),
                     ('col_dens', np.float64),
                     ('delta_v', np.float64),
                     ('vel_dispersion', np.float64),
                     ('interval_start', np.int32),
                     ('interval_end', np.int32)]

        # get name of columns and type of data for each
        name_type = line_info.copy()
        for f in fields:
            name_type.append( (f, np.float64) )

        n_feat = len(line_info)+len(fields)
        n_abs = len(self.ice_intervals)

        if n_abs == 0:
            print("No absorbers in ray: ", self.ray)
            return None
        #initialize empty table
        stats_table = QTable(np.empty(n_abs , dtype=name_type))

        #add ion name and wavelength
        stats_table['name']= self.ion_name
        stats_table['wave'] = self.wavelength_center
        stats_table['redshift'] = self.ds.current_redshift

        # fill table with absorber features
        for i in range(n_abs):
            #load data for calculating properties
            start, end = self.ice_intervals[i]
            stats_table['interval_start'][i] = start
            stats_table['interval_end'][i] = end
            dl = self.data['dl'][start:end].in_units('cm')
            density = self.data[('gas', 'density')][start:end].in_units('g/cm**3')
            tot_density = np.sum(dl*density)

            #calculate column density
            ion_field = ion_p_num(self.ion_name)
            ion_density=self.data[ion_field][start:end].in_units('cm**-3')
            col_density = np.sum(dl*ion_density)

            stats_table['col_dens'][i] = np.log10(col_density)

            #calculate delta_v of absorber
            vel_los_dat = self.data['velocity_los'][start:end].in_units('km/s')
            central_vel = np.sum(dl*ion_density*vel_los_dat)/col_density
            stats_table['delta_v'][i] = central_vel

            #calculate velocity dispersion
            #weighted std dev. weight=dl*ion_density

            # set single cell absorber to zero velocity variance
            if end-start == 1:
                vel_variance=0.
            else:
                vel_variance=col_density \
                     *np.sum(dl*ion_density * ( vel_los_dat - self.ds.quan(central_vel, 'km/s') )**2) \
                     /(col_density**2 - np.sum( (dl*ion_density)**2 ))

            stats_table['vel_dispersion'][i] = np.sqrt(vel_variance)

            #calculate other field averages
            for fld in fields:
                fld_data = self.data[fld][start:end]
                avg_fld = np.sum(dl*density*fld_data)/tot_density

                if fld in unit_dict.keys():
                    stats_table[fld][i] = avg_fld.in_units( unit_dict[fld] )
                else:
                    stats_table[fld][i] = avg_fld

        self.ice_table = stats_table
        return stats_table

    def get_spectacle_absorbers(self):
        """
        Uses spectacle to fit a trident made spectra of the specified ion.

        Returns
        ----------
        line_stats : astropy.QTable
            Table including all line statistics found from spectacle's fit of
            the spectra.
        """
        #create spectra for a single line to fit
        wav = int( np.round(self.wavelength_center) )
        line = f"{self.ion_name} {wav}"
        #format ion correctly to fit
        ion_wav= "".join(line.split())

        vel_array, flux_array=self._create_spectra()

        #constrain possible column density values
        #create line model
        line_finder = LineFinder1D(ions=[ion_wav], continuum=1, z=0,
                                   defaults=self.defaults_dict,fitter_args={'maxiter':2000},
                                   threshold=0.01, output='flux', min_distance=self.velocity_res, auto_fit=True)
        #fit data
        try:
            spec_model = line_finder(vel_array*u.Unit('km/s'), flux_array)
        except RuntimeError:
            print('fit failed(prolly hit max iterations)', self.ray)
            spec_model = None
        except IndexError:
            print('INDEX ERROR on', self.ray)
            spec_model = None

        #check if fit found any lines
        if spec_model is None:
            print('line could not be fit on ray ', self.ray)
            self.spectacle_model = None
            line_stats = None
            self.num_spectacle = 0

        else:
            init_stats = spec_model.line_stats(vel_array*u.Unit('km/s'))

            # include only lines greater than absorber_min
            line_indxs, = np.where( init_stats['col_dens'] >= self.absorber_min)
            if line_indxs.size == 0:
                print('line could not be fit on ray ', self.ray)
                self.spectacle_model = None
                line_stats = None
                self.num_spectacle = 0

            else:
                # retrieve lines that pass col dense threshold
                good_lines=[]
                for i in line_indxs:
                    good_lines.append(spec_model.lines[i])

                #create and save new model with lines desired
                self.spectacle_model = spec_model.with_lines(good_lines, reset=True)
                self.num_spectacle = len(good_lines)
                line_stats=self.spectacle_model.line_stats(vel_array*u.Unit('km/s'))

                #add redshift
                line_stats['redshift'] = self.ds.current_redshift

        self.spectacle_table = line_stats
        return line_stats

    def run_ice(self):
        """
        iteratively run the cloud method to extract all the absorbers in the
        lightray.

        Returns
        --------

        final_intervals: list of tuples of int
            List of the indices that indicate the start and end of each absorber.
        """
        num_density = self.data[ion_p_num(self.ion_name)].in_units("cm**(-3)")
        dl_list = self.data['dl'].in_units('cm')
        l_list = self.data['l'].in_units('cm')
        vel_los = self.data['velocity_los'].in_units('km/s')
        density_array = self.data[('gas', 'density')]


        all_intervals=[]
        curr_num_density = num_density.copy()
        curr_col_density = np.sum(num_density*dl_list)
        min_col_density = 10**self.absorber_min
        count=0

        while curr_col_density > min_col_density:
            #calc threshold to get fraction from current num density
            curr_thresh = self._cloud_method(curr_num_density, coldens_fraction=self.frac)

            #extract intervals this would cover
            curr_intervals = self._identify_intervals(num_density, curr_thresh)
            new_intervals = self._sensible_combination(all_intervals, curr_intervals, vel_los, dl_list,l_list, density_array)
            all_intervals = new_intervals.copy()

            #mask density array above threshold and apply mask to dl
            curr_num_density = np.ma.masked_greater_equal(num_density, curr_thresh)
            curr_dl =  np.ma.masked_array(dl_list, curr_num_density.mask)

            #calc leftover column density
            curr_col_density = np.sum(curr_num_density*curr_dl)
            count+=1

        #make sure intervals have high enough col density
        final_intervals=[]
        for b, e in all_intervals:
            lcd = np.log10(np.sum(dl_list[b:e]*num_density[b:e]))
            if lcd > self.absorber_min:
                final_intervals.append((b, e))
        return final_intervals

    def _create_spectra(self):
        """
        Use trident to create the absorption spectrum of the ray in velocity
        space for use in fitting.

        Returns
        --------
        velocity: YT array
            Array of velocity values of the generated spectra (in km/s)

        flux: YT array
            Array of the normalized flux values of the generated spectra

        """
        #set which ions to add to spectra
        wav = int( np.round(self.wavelength_center) )
        line = f"{self.ion_name} {wav}"
        ion_list = [line]

        # calc doppler redshift due to bulk motion
        if self.bulk_velocity is None:
            z_tot=self.redshift
        else:
            c = yt.units.c
            beta = self.bulk_velocity/c
            z_dopp = (1 - beta)/np.sqrt(1 +beta**2) -1
            z_dopp = z_dopp.value
            z_tot = (1+self.redshift)*(1+z_dopp) - 1

        #use auto feature to capture full line
        spect_gen = trident.SpectrumGenerator(lambda_min="auto", lambda_max="auto", dlambda = self.velocity_res, bin_space="velocity")
        spect_gen.make_spectrum(self.data, lines=ion_list)

        #get fields from spectra and give correct units
        flux = spect_gen.flux_field
        velocity = spect_gen.lambda_field

        return velocity, flux

    def _cloud_method(self, num_density_arr, coldens_fraction):
        "run the cloud method"
        cut = 0.999
        total = np.sum(num_density_arr)
        ratio = 0.001
        while ratio < coldens_fraction:
            part = np.sum(num_density_arr[num_density_arr > cut * np.max(num_density_arr)])
            ratio = part / total
            cut = cut - 0.001

        threshold = cut * np.max(num_density_arr)

        return threshold

    def _sensible_combination(self, prev_intervals, curr_intervals, velocity_array, dl_array, l_array, density_array):
        """
        adds new intervals by taking into account the velocities when combining them

        Parameters
        -----------
        prev_intervals : list
            the intervals already calculated

        curr_intervals : list
            the intervals that need to be added/combined

        velocity_array : array
            array of the line of sight velocity along ray

        dl_array : array
            cell lengths along the ray's path.

        density_array : array
            array of gas density. used to weight avg velocity for a given interval.

        Returns
        --------
        new_intervals : list
            a final list of intervals where prev and curr are properly combined.
        """
        # first check no region jumping (from use of cut_regions)
        if self.cut_region_filters is not None:
            #make sure spatially connected
            real_intervals = []
            for curr_b, curr_e in curr_intervals:
                #check if lengths match up
                size_dl = np.sum(dl_array[curr_b:curr_e])
                size_l = l_array[curr_e] - l_array[curr_b]
                rel_diff = abs(size_dl - size_l)/size_dl
                #print("rel diff: ", rel_diff)
                if rel_diff > 1e-12:
                    print(curr_b, curr_e)
                    # make sure things are good
                    divide_indx=None
                    for i in range(curr_b, curr_e):
                        # find where the jump is

                        rel_diff = abs(l_array[i] +dl_array[i] - l_array[i+1])/l_array[i]
                        #print(i, rel_diff.value)
                        if rel_diff > 1e-12:
                            divide_indx=i
                            break
                    #append intervals split up by the jump
                    if divide_indx is not None:
                        print(divide_indx)
                        real_intervals.append((curr_b, divide_indx))
                        real_intervals.append((divide_indx+1, curr_e))
                    else:
                        print("couldn't divide index for ",curr_b, " ", curr_e)

                else:
                    real_intervals.append((curr_b, curr_e))
            curr_intervals = real_intervals.copy()


        #check if there are any previous intervals to combine with
        if prev_intervals == []:
            return curr_intervals

        new_intervals=prev_intervals.copy()
        del_v = self.ds.quan(self.spectacle_res, 'km/s')

        #loop through current intervals
        for curr_b, curr_e in curr_intervals:

            overlap_intervals=[]
            #loop through all previous intervals
            for b,e in new_intervals:
                #check if previous interval is nested in curr interval
                if curr_b <= b and curr_e >= b:
                    #print(f"interval ({curr_b}, {curr_e}) overlap with ", b, e)
                    if curr_b <= e and curr_e >= e:
                        overlap_intervals.append((b, e))

                    #check if just beginning point enclose
                    else:
                        err_file = open("error_file.txt", 'a')
                        err_file.write(f"{self.ray_filename} had an intersection that wasn't complete :/")
                        err_file.close()
                #check if just endpoint enclosed
                elif curr_b <= e and curr_e >= e:
                    err_file = open("error_file.txt", 'a')
                    err_file.write(f"{self.ray_filename} had an intersection that wasn't complete :/")
                    err_file.close()

            #
            #
            #This is such a mess below but it works
            #hopefully I'll think of a much cleaner way to do this
            #but for now this is it
            #
            #

            if overlap_intervals == []:
                new_intervals.append((curr_b, curr_e))
            else:

                #collect overlap points into list
                points = [curr_b]
                for b, e in overlap_intervals:
                    #print(f"curr {curr_b, curr_e} ovelaps {b, e}")
                    new_intervals.remove((b, e))
                    points.append(b)
                    points.append(e)
                points.append(curr_e)

                avg_v=[]
                for i in range(len(points)-1):
                    pnt1, pnt2 = points[i], points[i+1]
                    #find weighted avg velocity
                    vel = np.sum(density_array[pnt1:pnt2]*dl_array[pnt1:pnt2]*velocity_array[pnt1:pnt2]) \
                          /np.sum(density_array[pnt1:pnt2]*dl_array[pnt1:pnt2])
                    avg_v.append((vel, pnt1, pnt2))

                start_b = curr_b
                for i in range(len(avg_v)-1):
                    #if velocity difference is greater than threshold
                    if abs(avg_v[i][0] - avg_v[i+1][0]) > del_v:
                        #create new interval
                        new_intervals.append((start_b, avg_v[i][2]))
                        #change start of next interval
                        start_b = avg_v[i][2]
                    #check if this is the last two intervals to check
                    if i == len(avg_v) -2:
                        new_intervals.append((start_b, curr_e))


        return new_intervals

    def _identify_intervals(self, field, cutoff):
        """
        Find the intervals for absorbers using some cutoff on a
        field (generally number density) along lightray.

        Parameters
        -----------
        field : array/list
            list of values to compare to cutoff
        cutoff : double
            threshold defining where absorbers are.

        Returns
        -----------
        intervals : list of tuples
            list of the intervals defining the absorbers in this ray.
        """
        in_absorber = False
        intervals = []

        #Iterate over values in field
        for i,value in enumerate(field):
            #Check if started an absorber and if above cutoff
            if in_absorber and value < cutoff:
                in_absorber = False
                #add interval to list
                intervals.append((start,i))
            # check if just entered an absorber
            elif not in_absorber and value >= cutoff:
                in_absorber = True
                start = i
            else:
                continue
        #check if was still in absorber when hitting end of ray
        if in_absorber and start != i:
            intervals.append((start, i))
        return intervals
