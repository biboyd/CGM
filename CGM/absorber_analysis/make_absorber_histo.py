import numpy as np
import matplotlib.pyplot as plt
import yt
import trident
from os import makedirs
import sys


def construct_histo(dsname, max_b, frac, ion, column='col density', spectacle=True,cgm='CGM', bins=30, outname='./plot.png'):
    ion_under=f"{ion.split()[0]}_{ion.split()[1]}"

    scratch_dir="/mnt/gs18/scratch/users/boydbre1/"
    ds_fname = f"{scratch_dir}/cosmological/foggie/{dsname}/{dsname}"
    arr_dir=f"{scratch_dir}/metallicity_analysis/foggie/{dsname}/max_impact{max_b}/output_{cgm}{frac}/ion_{ion_under}"
    ray_dir=f"{scratch_dir}/metallicity_analysis/foggie/{dsname}/max_impact{max_b}/rays"

    try:
        absorber_array=np.load(f"{arr_dir}/all_absorbers.npy")
        header = np.load(f"{arr_dir}/absorber_info_header.npy")
    except FileNotFoundError:
        print(f"Couldn't find file for {dsname} {ion} {max_b}")
        return 1
    indx = np.where(header == column)
    abs_column = absorber_array[:, indx]
    r = yt.load(ds_fname).current_redshift

    fig = plt.figure()
    plt.hist(abs_column, bins=bins)
    plt.title(f"{ion} z={r:.2f} max_b={max_b} kpc {cgm}")

    plt.xlabel(f"{col density} {ion}")
    plt.ylabel(f"Count")
    plt.annotate(f"num absorbers: {abs_column.size}", (0.65, 0.9), xycoords='axes fraction')
    plt.savefig(outname)
    plt.close(fig)
    return 0

def all_histo(dsname_list, max_b, frac, ion, cgm='', column='col density', bins=50, histo_type='stepfilled',linewidth=1,alpha=0.5, ax=None):
    scratch_dir="/mnt/gs18/scratch/users/boydbre1/"
    ion_under=f"{ion.split()[0]}_{ion.split()[1]}"

    if ax is None:
        fig, ax = plt.subplots(1)
    else:
        fig = ax.figure

    for dsname in dsname_list:
        ds_fname = f"{scratch_dir}/cosmological/foggie/{dsname}/{dsname}"
        arr_dir=f"{scratch_dir}/metallicity_analysis/foggie/{dsname}/max_impact{max_b}/output_{cgm}{frac}/ion_{ion_under}"
        ray_dir=f"{scratch_dir}/metallicity_analysis/foggie/{dsname}/max_impact{max_b}/rays"
        r = yt.load(ds_fname).current_redshift

        try:
            absorber_array=np.load(f"{arr_dir}/all_absorbers.npy")
            header = np.load(f"{arr_dir}/absorber_info_header.npy")
        except FileNotFoundError:
            print(f"Couldn't find file for {dsname} {ion} {max_b}")
            return 1
        indx = np.where(header == column)
        abs_column = absorber_array[:, indx]
        n_abs = abs_column.size
        #lcd_norm = abs_column/n_abs

        histo, edges= np.histogram(abs_column,  range=(13, 14.75), bins=bins)
        histo = histo/n_abs

        ax.hist(edges[:-1], edges, weights=histo, histtype=histo_type, label=f"z={r:.2f}: {n_abs}",linewidth=linewidth, alpha=alpha)
        ax.set_title(f"{ion} Absorber Distribution")
        ax.set_xlabel(f"Log Col Density {ion}")
        ax.set_ylabel(f"Count/num_absorbers")

    ax.legend()
    return fig, ax

def scatter_plot(dsname_list, max_b, frac, ion, column='col density', ax=None, cgm=''):
    scratch_dir="/mnt/gs18/scratch/users/boydbre1/"
    ion_under=f"{ion.split()[0]}_{ion.split()[1]}"
    if ax is None:
        fig, ax = plt.subplots(1)
    else:
        fig = ax.figure


    n_abs = []
    redshift = []
    for dsname in dsname_list:
        ds_fname = f"{scratch_dir}/cosmological/foggie/{dsname}/{dsname}"
        arr_dir=f"{scratch_dir}/metallicity_analysis/foggie/{dsname}/max_impact{max_b}/output_{cgm}{frac}/ion_{ion_under}"
        ray_dir=f"{scratch_dir}/metallicity_analysis/foggie/{dsname}/max_impact{max_b}/rays"
        r = yt.load(ds_fname).current_redshift

        try:
            absorber_array=np.load(f"{arr_dir}/all_absorbers.npy")
            header = np.load(f"{arr_dir}/absorber_info_header.npy")
        except FileNotFoundError:
            print(f"Couldn't find file for {dsname} {ion} {max_b}")
            return 1
        indx = np.where(header == column)
        abs_column = absorber_array[:, indx]
        n_abs.append(abs_column.size)
        redshift.append(r)

    ax.plot(redshift, n_abs, '-o')
    ax.set_xlabel("Redshift")
    ax.set_ylabel("Number of Absorbers")

    ax.set_xlim(max(redshift) +0.1, min(redshift) - 0.1)
    ax.set_title(f"{ion} absorber log col dense > 13")
    return fig, ax

if __name__ == '__main__':
    ds_names = ['RD0018', 'RD0020', 'RD0027', 'RD0032', 'RD0034', 'RD0035', 'RD0036']
    #ds_names = ['RD0018', 'RD0020', 'RD0027',  'RD0036']

    max_b = 200
    frac = 0.8
    ion = sys.argv[1]
    outdir = sys.argv[2]
    cgm = sys.argv[3]

    makedirs(outdir, exist_ok=True)
    if cgm == 'CGM':
        pass
    else:
        cgm=''

    #for ds in ds_names:
    #    construct_histo(ds, max_b, frac, ion, cgm=cgm, outname=f"{outdir}/histo{ds}.png")

    all_histo(ds_names, max_b, frac, ion, cgm=cgm, outname=f"{outdir}/all.png")
