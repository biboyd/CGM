import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# set indirectory
max_imp=200
data_dir=f"/mnt/home/boydbre1/data/absorber_data/cool_refinement//max_impact{max_imp}/ion_O_VI/"
cut_dir="cgm"
in_dir=f"{data_dir}/{cut_dir}/old"

# collect catalogs from each rshift
tab_list=[]
for ds_num in range(20, 43):
    try:
        #tab_list.append( Table.read(f"{in_dir}/RD00{ds_num}_absorbers.h5") )
        curr_df = pd.read_csv(f"{data_dir}/RD00{ds_num}_absorbers.csv", index_col=0)
        tab_list.append(curr_df)
    except OSError:
        print(f"couldn't load table for {ds_num}")

# make master catalog
df = pd.concat(tab_list)

# set x/y vars
varx="radius_corrected"
vary="radial_velocity_corrected"

rshifts = df['redshift'].unique()

# make scatter plots
fig_temp = many_rvel_v_r('temperature', 'Reds')
fig_metal = many_rvel_v_r('metallicity', 'Greens')
fig_density = many_rvel_v_r('density', 'Blues')

#save scatter plots 
outdir="/mnt/home/boydbre1/data/absorber_data/cool_refinement/max_impact200/ion_O_VI/plots/cgm/scatter_plots"
makedirs(outdir, exist_ok=True)
fig_temp.savefig(f"{outdir}/radvel_v_rad_temperature.png", dpi=300)
fig_metal.savefig(f"{outdir}/radvel_v_rad_metallicity.png", dpi=300)
fig_density.savefig(f"{outdir}/radvel_v_rad_density.png", dpi=300)

def many_rvel_v_r(z, cmap, log=True, zrange=None, symlog=False):
    rows=4
    cols=6
    if zrange is None:
        if log:
            zlow, zhigh=ovi_range_dict[f"log_{z}"]
        else:
            if z in ovi_range_dict.keys():
                zlow, zhigh=ovi_range_dict[f"{z}"]
            else:
                zlow = df[z].min()
                zhigh=df[z].max()
    else:
        zlow, zhigh=zrange
    fig, axes = plt.subplots(rows, cols, figsize=(18, 10), sharex=True, sharey=True)

    #h, xedges, yedges, something =plt.hist2d(df[varx], df[vary], bins=50)
    #my_range=[[xedges[0], xedges[-1]],[yedges[0], yedges[-1]]]
    j=-1
    for i in range(cols*rows):
        if i%cols == 0:
            j+=1
        ax =axes[j,i%cols]
        ax.set_frame_on(False)
        ax.grid()
        ax.tick_params(axis='both', which='both', bottom=False, left=False)

        if i < len(rshifts):
            if log:
                s=ax.scatter(tab_list[i][varx], tab_list[i][vary],
                                marker='.',
                                c=np.log10(tab_list[i][z]), cmap=cmap, vmin=zlow, vmax=zhigh, label=f"z={rshifts[i]:0.2f}")
            elif symlog:
                s=ax.scatter(tab_list[i][varx], tab_list[i][vary],
                                marker='.', norm=colors.SymLogNorm(linthresh=0.03, linscale=0.03,
                                                  vmin=zlow, vmax=zhigh),
                                c=tab_list[i][z], cmap=cmap, vmin=zlow, vmax=zhigh)
            else:
                s=ax.scatter(tab_list[i][varx], tab_list[i][vary],
                                marker='.',
                                c=tab_list[i][z], cmap=cmap, vmin=zlow, vmax=zhigh)


            ax.annotate(f"z={rshifts[i]:0.2f}", (0.55, 0.875), xycoords='axes fraction')
            #ax.set_title(f"Redshift {rshifts[i]:0.2f}")
            #ax.legend()
            ax.set_ylim(-300, 300)
            ax.hlines(0, -10, 210, linestyle='--')

    #fig.delaxes(axes[j, -1])

    xlab= axis_labels_dict[varx]
    ylab = axis_labels_dict[vary]

    """
    axes[-1,0].set_xlabel(xlab)
    axes[-1,1].set_xlabel(xlab)

    axes[-1,2].set_xlabel(xlab)
    axes[-2,3].set_xlabel(xlab)


    axes[0, 2].get_shared_x_axes().join(axes[0, 2], axes[1, 2])
    """

    fig.text(0.07, 0.5, ylab, ha='center', va='center', size='large',rotation='vertical')
    for j in range(cols):
        axes[-1, j].set_xlabel(xlab)
    #for i in range(rows):
    #    axes[i,0].set_ylabel(ylab)
    cb=fig.colorbar(s, ax=axes, location='right', shrink=1)
    if log:
        cb.set_label(axis_labels_dict[f"log_{z}"])
    else:
        if z in axis_labels_dict.keys():
            cb.set_label(axis_labels_dict[f"{z}"])
        else:
            cb.set_label(f"{z}")
    #fig.tight_layout()
    return fig
