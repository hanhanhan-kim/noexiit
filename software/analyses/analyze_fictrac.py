#!/usr/bin/env python3

"""
Process and visualize FicTrac data with helper functions. 
When run as a script, transforms .dat FicTrac files into a single concatenated \
Pandas dataframe with some additional columns. Then performs various processing \
and plotting of the FicTrac data. Includes visualization of the frequency domain, \
low-pass Butterworth filtering, XY path with a colour map, ___. 
"""

import argparse
import glob
from sys import exit, path
from os.path import join, expanduser
from os import mkdir
import re

import numpy as np
import pandas as pd
import scipy.interpolate as spi
import scipy.signal as sps
import scipy.signal as sps

from bokeh.io import output_file, export_png, export_svgs, show
from bokeh.transform import linear_cmap
from bokeh.plotting import figure
from bokeh.models import ColorBar, ColumnDataSource, Span
from bokeh.layouts import gridplot
from bokeh.palettes import brewer
import colorcet as cc

from fourier_transform import fft, bokeh_freq_domain

# TODO: Sym link my local into noexiit src? 
path.insert(1, expanduser('~/src/cmocean-bokeh'))
from cmocean_cmaps import get_all_cmocean_colours


def get_framerate_from_logs(log):
    """
    Compute the average framerate in Hz from a FicTrac .log file. 
    
    Parameters:
    -----------
    log (str): Path to the FicTrac .log file. 

    Returns:
    --------
    Mean framerate in Hz (float). 
    """

    with open (log, "r") as f:

        log_lines = f.readlines()

        hz_lines = []
        for line in log_lines:
            if "frame rate" in line:
                # Pull out substring between [in/out] and [:
                result = re.search("\[in/out]: (.*) \[", line)
                hz_lines.append(float(result.group(1)))

    return np.mean(hz_lines)


def parse_dats(root, nesting, ball_radius, framerate=None):
    """
    Batch processes subdirectories, where each subdirectory is labelled 'fictrac'
    and has a single FicTrac .dat file and a corresponding .log file. Returns a 
    single concatenated dataframe. 
    
    The output dataframe is given proper headings, as informed by 
    the documentation on rjdmoore's FicTrac GitHub page. 

    The framerate is computed for each .dat, by taking the average frame rate
    specified in the corresponding .log. 

    Elapsed time is converted into seconds and minutes, and the integrated 
    X and Y positions are converted to real-world values, by multiplying them 
    against the ball radius. 
    
    Parameters:
    -----------
    root (str): Absolute path to the root directory. I.e. the outermost 
        folder that houses the FicTrac .avi files

    nesting (int): Specifies the number of folders that are nested from the
        root directory. I.e. the number of folders between root and the
        'fictrac' subdirectory that houses the input .dat and .log files. E.g. 1.

    ball_radius (float): The radius of the ball (mm) the insect was on. 
        Used to compute the real-world values in mm.  

    framerate (float): The mean framerate used for acquisition with FicTrac. 
        If None, will compute the average framerate for each .dat, from its 
        corresponding .log. Can be overridden with a provided manual value. 
        Default is None. 

    Returns:
    --------
    A single Pandas dataframe that concatenates all the input .dat files.
    """

    confirm = input(f"The ball_radius argument must be in mm. Confirm by inputting 'y'. Otherwise, hit any other key to quit.")
    while True:
        if confirm.lower() == "y":
            break
        else:
            exit("Re-run this function with a ball_radius that's in mm.")

    logs = sorted(glob.glob(join(root, nesting * "*/", "fictrac/*.log"))) 
    dats = sorted(glob.glob(join(root, nesting * "*/", "fictrac/*.dat")))
    
    headers = [ "frame_cntr",
                "delta_rotn_vector_cam_x", 
                "delta_rotn_vector_cam_y", 
                "delta_rotn_vector_cam_z", 
                "delta_rotn_err_score", 
                "delta_rotn_vector_lab_x", 
                "delta_rotn_vector_lab_y", 
                "delta_rotn_vector_lab_z",
                "abs_rotn_vector_cam_x", 
                "abs_rotn_vector_cam_y", 
                "abs_rotn_vector_cam_z",
                "abs_rotn_vector_lab_x", 
                "abs_rotn_vector_lab_y", 
                "abs_rotn_vector_lab_z",
                "integrat_x_posn",
                "integrat_y_posn",
                "integrat_animal_heading",
                "animal_mvmt_direcn",
                "animal_mvmt_spd",
                "integrat_fwd_motn",
                "integrat_side_motn",
                "timestamp",
                "seq_cntr",
                "delta_timestamp",
                "alt_timestamp" ]

    if framerate is None: 
        # Compute framerates from .log files:
        framerates = []
        for log in logs:
            hz = get_framerate_from_logs(log)
            framerates.append(hz)

    else: 
        assert(float(framerate)), \
            "'framerate' must be a float, if inputting manually."
    
    dfs = []
    for i, dat in enumerate(dats):
        with open(dat, 'r') as f:
            next(f) # skip first row
            df = pd.DataFrame((l.strip().split(',') for l in f), columns=headers)

        # Convert all values to floats:
        df = df[headers].astype(float)

        # Convert the values in the frame and sequence counters columns to ints:
        df['frame_cntr'] = df['frame_cntr'].astype(int)
        df['seq_cntr'] = df['seq_cntr'].astype(int)

        # Compute average framerate:
        if framerate is None:
            # Add framerates from .logs:
            f_rate = framerates[i] 

        df['avg_framerate'] = f_rate

        # Compute real-world values:
        df['X_mm'] = df['integrat_x_posn'] * ball_radius
        df['Y_mm'] = df['integrat_y_posn'] * ball_radius
        df['speed_mm_s'] = df['animal_mvmt_spd'] * f_rate * ball_radius

        # Compute elapsed time:
        df['secs_elapsed'] = df['frame_cntr'] / f_rate
        df['mins_elapsed'] = df['secs_elapsed'] / 60
        
        # Discretize minute intervals as strings:
        df['min_int'] = df['mins_elapsed'].astype('int') + 1
        df['min_int'] = df['min_int'].apply(str)

        # Assign animal number:
        df['animal'] = i 

        dfs.append(df)

    dfs = pd.concat(dfs)
        
    return dfs


def unconcat_df(dfs, col_name="animal"):
    """
    Splits up a concatenated dataframe according to each unique animal.
    Returns a list of datafrmaes. 

    Parameters:
    -----------
    dfs: A Pandas dataframe
    col_name (str): A column name in 'dfs' with which to split into smaller dataframes. 
        Default is "animal". 

    Returns:
    --------
    A list of dataframes, split up by each unique animal. 
    """

    assert (col_name in dfs), \
        f"The column, {col_name}, is not in in the input dataframe, {dfs}"

    dfs_list = []

    for _, df in enumerate(dfs[col_name].unique()):
        df = dfs.loc[dfs[col_name]==df]
        dfs_list.append(df)

    return(dfs_list)


def plot_fictrac_fft(dfs, val_col, time_col, 
                    even=False, window=np.hanning, pad=1, 
                    cutoff_freq=None, 
                    save_path=None, show_plots=True):  
    """
    Perform a Fourier transform on FicTrac data for each animal. Generate 
    frequency domain plots for each animal. Outputs plots. 

    Parameters:
    ------------
    dfs (DataFrame): Concatenated dataframe of FicTrac data generated from 
        parse_dats()

    val_col (str): Column name of the dfs dataframe to be Fourier-transformed.  

    time_col (str): Column name of the dfs dataframe that specifies time in 
        in SECONDS. 

    even (bool): If False, will interpolate even sampling. 

    cutoff_freq (float): x-intercept value for plotting a vertical line. 
        To be used to visualize a candidate cut-off frequency. Default is None.

    save_path (str): Absolute path to which to save the plots as .png files. 
        If None, will not save the plots. Default is None. 

    show_plots (bool): If True, will show plots, but will not 
        output a list of Bokeh plotting objects. If False, will not show 
        plots, but will output a list of Bokeh plotting objects. If both 
        save and show_plots are True, .html plots will be generated, in addition 
        to the .png plots. Default is True.

    Returns:
    ---------
    if show_plots is True: will show plots but will not output bokeh.plotting.figure
         object.

    if show_plots is False: will output a list of bokeh.plotting.figure objects, 
        but will not show plots.

    if save is True: will save .png plots.
    
    if both show_plots and save are True, will show plots and save .png and .html 
        plots. 

    if both show_plots and save are False, will return nothing. 
    """
    if ("sec" or "secs") not in time_col:
        safe_secs = input(f"The substrings 'sec' or 'secs' was not detected in the 'time_col' variable, {time_col}. The units of the values in {time_col} MUST be in seconds. If the units are in seconds, please input 'y'. Otherwise input anything else to exit.")
        while True:
            if safe_secs.lower() == "y":
                break
            else:
                exit("Re-run this function with a 'time_col' whose units are secs.")

    dfs_list = unconcat_df(dfs, col_name="animal")

    bokeh_ps = []
    for _, df in enumerate(dfs_list): 

        assert (len(df[time_col] == len(df[val_col]))), \
            "time and val are different lengths! They must be the same."
        assert (val_col in dfs), \
            f"The column, {val_col}, is not in the input dataframe, {dfs}"
        assert (time_col in dfs), \
            f"The column, {time_col}, is not in the input dataframe, {dfs}"
        assert ("animal" in dfs), \
            f"The column 'animal' is not in in the input dataframe, {dfs}"

        time = list(df[str(time_col)])
        val = list(df[str(val_col)])

        # Fourier-transform:
        f = spi.interp1d(time, val)

        if even is False:
            time_interp = np.linspace(time[0], time[-1], len(time))
            val_interp = f(time_interp)
        else:
            time_interp = time
            val_interp = val

        amp, _, freq = fft( val_interp, 
                            time_interp, 
                            pad=1, 
                            window=window, 
                            post=True)

        # Plot:
        p1, p2 = bokeh_freq_domain(freq, amp)

        p1.title.text = f"frequency domain"
        p1.title.text_font_size = "16pt"
        p1.yaxis.axis_label_text_font_size = "12pt"
        p2.yaxis.axis_label_text_font_size = "12pt"
        p2.xaxis.axis_label_text_font_size = "12pt"

        if cutoff_freq is not None:
            float(cutoff_freq)
            cutoff_line = Span(location=cutoff_freq, 
                               dimension="height", 
                               line_color="#e41a1c",
                               line_dash="dashed",
                               line_width=2)
            p1.add_layout(cutoff_line)
            p2.add_layout(cutoff_line)

        p = gridplot([p1, p2], ncols=1)

        # Output:
        if save_path is not None:
            filename = save_path + f"fictrac_freqs"

            # Bokeh does not atm support gridplot svg exports
            export_png(p, filename = filename + ".png")
            output_file(filename = filename + ".html", 
                        title=f"fictrac_freqs")

        if show_plots is True:
            show(p)
        else:
            bokeh_ps.append(p)
        
    if show_plots is False:
        return bokeh_ps


def plot_fictrac_filter(dfs, val_col, time_col, 
                        order, cutoff_freq,  
                        framerate=None,
                        val_label=None, time_label=None,
                        view_perc=1.0, 
                        save_path=None, show_plots=True):
    """
    Apply a low-pass Butterworth filter on offline FicTrac data. 

    Parameters:
    -----------
    dfs (DataFrame): Concatenated dataframe of FicTrac data generated from 
        parse_dats()

    val_col (str): Column name of the dfs dataframe to be Fourier-transformed.  

    time_col (str): Column name of the dfs dataframe that specifies time. 

    order (int): Order of the filter.

    cutoff_freq (float): The cutoff frequency for the filter in Hz.

    framerate (float): The mean framerate used for acquisition with FicTrac. 
        If None, will use the average frame rate as computed in the input 'dfs'. 
        Can be overridden with a provided manual value. Default is None.

    val_label (str): Label for the plot's y-axis. 

    time_label (str): Label for the plot's time-axis. 

    view_perc (float): Specifies how much of the data to plot as an initial \
        percentage. Useful for assessing the effectieness of the filter over longer \
        timecourses. Default is set to 1, i.e. plot the data over the entire \
        timecourse. Must be a value between 0 and 1.

    save_path (str): Absolute path to which to save the plots as .png and .svg files. 
        If None, will not save the plots. Default is None. 

    show_plots (bool): If True, will show plots, but will not 
        output a list of Bokeh plotting objects. If False, will not show 
        plots, but will output a list of Bokeh plotting objects. If both 
        save and show_plots are True, .html plots will be generated, in addition 
        to the .svg and .png plots. Default is True.

    Returns:
    --------
    if show_plots is True: will show plots but will not output bokeh.plotting.figure
         object.

    if show_plots is False: will output a list of bokeh.plotting.figure objects, 
        but will not show plots.

    if save is True: will save .svg and .png plots.
    
    if both show_plots and save are True, will show plots and save .svg, .png and 
        .html plots. 

    if both show_plots and save are False, will return nothing. 
    """
    
    assert (0 <= view_perc <= 1), \
        f"The view percentage, {view_perc}, must be between 0 and 1."
    
    dfs_list = unconcat_df(dfs, col_name="animal")

    bokeh_ps = []
    for _, df in enumerate(dfs_list):
        
        assert (len(df[time_col] == len(df[val_col]))), \
            "time and val are different lengths! They must be the same."
        assert (time_col in dfs), \
            f"The column, {time_col}, is not in the input dataframe, {dfs}"
        assert (val_col in dfs), \
            f"The column, {val_col}, is not in the input dataframe, {dfs}"
        assert ("animal" in dfs), \
            f"The column 'animal' is not in in the input dataframe, {dfs}"
        
        if framerate is None:
            framerate = df["avg_framerate"][0]

        time = list(df[str(time_col)])
        val = val = list(df[str(val_col)])

        # Design low-pass filter:
        b, a = sps.butter(int(order), float(cutoff_freq), fs=framerate)
        # Apply filter:
        val_filtered = sps.lfilter(b, a, val)
        
        # View the first _% of the data:
        domain = int(view_perc * len(val))
        
        # Plot:
        if val_label is None:
            val_label = val_col.replace("_", " ")
        if time_label is None:
            time_label = time_col.replace("_", " ")
        
        p = figure(
        background_fill_color="#efe8e2",
        width=1600,
        height=500,
        x_axis_label=time_label,
        y_axis_label=val_label 
        )

        p.line(
            x=time[:domain],
            y=val[:domain],
            color=brewer["Paired"][3][0],
            legend_label="raw"
        )
        p.line(
            x=time[:domain],
            y=val_filtered[:domain],
            color=brewer["Paired"][3][1],
            legend_label="filtered"
        )
        
        p.title.text = f"first {view_perc * 100}% with butterworth filter: cutoff = {cutoff_freq} Hz, order = {order}"
        p.title.text_font_size = "14pt"
        p.yaxis.axis_label_text_font_size = "12pt"
        p.yaxis.axis_label_text_font_size = "12pt"
        p.xaxis.axis_label_text_font_size = "12pt"
        
        # Output:
        if save_path is not None:
            filename = save_path + f"fictrac_filter"
            
            p.output_backend = "svg"
            export_svgs(p, filename=filename + ".svg")
            export_png(p, filename=filename + ".png")
            output_file(filename=filename + ".html", 
                        title=filename)
            
        if show_plots is True:
            # In case this script is run in Jupyter, change output_backend 
            # back to "canvas" for faster performance:
            p.output_backend = "canvas"
            show(p)
        else:
            bokeh_ps.append(p)
        
    if show_plots is False:
        return bokeh_ps


def plot_fictrac_XY_cmap(dfs, low=0, high_percentile=95, respective=False, 
                         cmap_col="speed_mm_s", cmap_label="speed (mm/s)", 
                         palette = cc.CET_L16, size=2.5, alpha=0.1, 
                         show_start=False, 
                         save_path=None, show_plots=True):
    """
    Plot XY FicTrac coordinates of the animal with a linear colourmap for 
    a FicTrac 
    variable of choice. 
    
    Parameters:
    -----------
    dfs (DataFrame): Concatenated dataframe of FicTrac data generated from 
        parse_dats()
    low (float): The minimum value of the colour map range. Any value below the set 
        'low' value will be 'clamped', i.e. will appear as the same colour as 
        the 'low' value. The 'low' value must be 0 or greater. Default value 
        is 0.
    high_percentile (float): The max of the colour map range, as a percentile of the 
        'cmap_col' variable's distribution. Any value above the 'high_percentile'
        will be clamped, i.e. will appear as the same colour as the 
        'high_percentile' value. E.g. if set to 95, all values below the 95th 
        percentile will be mapped to the colour map, and all values above the
        95th percentile will be clamped. 
    respective (bool): If True, will re-scale colourmap for each individual animal to 
        their respective 'high_percentile' cut-off value. If False, will use
        the 'high_percentile' value computed from the population, i.e. the
        concatenated 'dfs' dataframe. Default is False. 
    cmap_col (str): Column name of the dfs dataframe to be colour-mapped. 
    cmap_label (str): Label for the colour map. 
    palette (list): A list of hexadecimal colours to be used for the colour map.
    size (float): The size of each datapoint specifying XY location. 
    alpha(float): The transparency of each datapoint specifying XY location.
        Must be between 0 and 1.
    show_start (bool): If True, will plot a marking to explicitly denote the start 
        site. Default is False. 
    
    save_path (str): Absolute path to which to save the plots as .png and .svg files. 
        If None, will not save the plots. Default is None. 

    show_plots (bool): If True, will show plots, but will not 
        output a list of Bokeh plotting objects. If False, will not show 
        plots, but will output a list of Bokeh plotting objects. If both 
        save and show_plots are True, .html plots will be generated, in addition 
        to the .svg and .png plots. Default is True.

    Returns:
    --------
    if show_plots is True: will show plots but will not output bokeh.plotting.figure
         object.

    if show_plots is False: will output a list of bokeh.plotting.figure objects, 
        but will not show plots.

    if save is True: will save .svg and .png plots.
    
    if both show_plots and save are True, will show plots and save .svg, .png and 
        .html plots. 

    if both show_plots and save are False, will return nothing. 
    """
    assert (low >= 0), \
        f"The low end of the colour map range must be non-negative"
    assert ("X_mm" in dfs), \
        f"The column, 'X_mm', is not in the input dataframe, {dfs}"
    assert ("Y_mm" in dfs), \
        f"The column, 'Y_mm', is not in the input dataframe, {dfs}"
    assert (cmap_col in dfs), \
        f"The column, {cmap_col}, is not in the input dataframe, {dfs}"
    assert ("animal" in dfs), \
            f"The column 'animal' is not in in the input dataframe, {dfs}"
    
    dfs_list = unconcat_df(dfs, col_name="animal")
    
    if respective is False:
        high = np.percentile(dfs[cmap_col], high_percentile)

    bokeh_ps = []
    for _, df in enumerate(dfs_list):
        
        assert (len(df["X_mm"] == len(df["Y_mm"]))), \
            "X_mm and Y_mm are different lengths! They must be the same."
        
        source = ColumnDataSource(df)
        
        if respective is True:
            high = np.percentile(df[cmap_col], high_percentile)
            # also change colorbar labels from min -> max?
        
        mapper = linear_cmap(field_name=cmap_col, 
                             palette=palette, 
                             low=low, 
                             high=high)
        
        p = figure(background_fill_color="#efe8e2", 
                   width=800,
                   height=800,
                   x_axis_label="X (mm)",
                   y_axis_label="Y (mm)")
        
        p.circle(source=source,
                 x="X_mm",
                 y="Y_mm",
                 color=mapper,
                 size=size,
                 alpha=alpha)
        
        if show_start is True:
            # Other options include .cross, .circle_x, and .hex:
            p.circle(x=df["X_mm"][0], 
                     y=df["Y_mm"][0], 
                     size=12,
                     color="darkgray",
                     fill_alpha=0.5)

        color_bar = ColorBar(color_mapper=mapper['transform'], 
                             title=cmap_label,
                             title_text_font_size="7pt",
                             width=10,
                             location=(0,0))

        p.add_layout(color_bar, "right")

        p.title.text_font_size = "14pt"
        p.xaxis.axis_label_text_font_size = '10pt'
        p.yaxis.axis_label_text_font_size = '10pt'

        bokeh_ps.append(p)

        # Output:
        if save_path is not None:
            filename = save_path + f"fictrac_XY_speed"
            
            p.output_backend = "svg"
            export_svgs(p, filename=filename + ".svg")
            export_png(p, filename=filename + ".png")
            output_file(filename=filename + ".html", 
                        title=filename)
            
        if show_plots is True:
            # In case this script is run in Jupyter, change output_backend 
            # back to "canvas" for faster performance:
            p.output_backend = "canvas"
            show(p)
        else:
            bokeh_ps.append(p)
        
    if show_plots is False:
        return bokeh_ps


def main():

    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument("root",
        help="Absolute path to the root directory. I.e. the outermost \
            folder that houses the FicTrac files.\
            E.g. /mnt/2TB/data_in/test/")
    parser.add_argument("nesting", type=int,
        help="Specifies the number of folders that are nested from \
            the root directory. I.e. The number of folders between root \
            and the 'fictrac' subdirectory that houses the .dat and .log files. \
            This subdirectory MUST be called 'fictrac'.")
    parser.add_argument("ball_radius", type=float,
        help="The radius of the ball used with the insect-on-a-ball tracking rig. \
            Must be in mm.")
    parser.add_argument("val_col", 
        help="Column name of the Pandas dataframe to be used as the dependent \
            variable for analyses.")
    parser.add_argument("time_col",
        help="Column name of the Pandas dataframe specifying the time.")
    parser.add_argument("cmap_col",
        help="Column name of the Pandas dataframe specifying the variable to be \
            colour-mapped.")
    parser.add_argument("cutoff_freq", type=float,
        help="Cutoff frequency to be used for filtering the FicTrac data.")
    parser.add_argument("order", type=int,
        help="Order of the filter.")
    parser.add_argument("view_percent", type=float,
        help="Specifies how much of the data to plot as an initial \
            percentage. Useful for assessing the effectieness of the filter over \
            longer timecourses. Default is set to 1, i.e. plot the data over the \
            entire timecourse. Must be a value between 0 and 1.")

    parser.add_argument("val_label", nargs="?", default=None,
        help="y-axis label of the generated plots. Default is a formatted \
            val_col")
    parser.add_argument("time_label", nargs="?", default=None,
        help="time-axis label of the generated plots. Default is a formatted \
            time_col")
    parser.add_argument("cmap_label", nargs="?", default=None,
        help="label of the colour map legend")
    parser.add_argument("framerate", nargs="?", default=None, type=float,
        help="The mean framerate used for acquisition with FicTrac. \
            If None, will compute the average framerate. Can be overridden with a \
            provided manual value. Default is None.") 
    
    parser.add_argument("-ns", "--nosave", action="store_true", default=False,
        help="If enabled, does not save the plots. By default, saves plots.")
    parser.add_argument("-sh", "--show", action="store_true", default=False,
        help="If enabled, shows the plots. By default, does not show the plots.")
    args = parser.parse_args()

    root = args.root
    nesting = args.nesting 
    framerate = args.framerate 
    ball_radius = args.ball_radius # mm

    val_col = args.val_col
    val_label = args.val_label
    time_col = args.time_col
    time_label = args.time_label
    cmap_col = args.cmap_col
    cmap_label = args.cmap_label 
    cutoff_freq = args.cutoff_freq
    order = args.order
    view_perc = args.view_percent

    nosave = args.nosave
    show_plots = args.show 

    # Parse FicTrac inputs:
    concat_df = parse_dats(root, nesting, ball_radius, framerate)

    # Unconcatenate the concatenated df:
    dfs_list = unconcat_df(concat_df, col_name="animal")

    # Save each individual animal bokeh plot to its respective animal folder. 
    folders = sorted(glob.glob(join(root, nesting * "*/", "fictrac/")))

    for i, folder in enumerate(folders):

        mkdir(join(folder, "plots/"))
        df = dfs_list[i]

        if nosave is False:
            save_path = join(folder, "plots/")
        elif nosave is True:
            save_path = None

        # Plot FFT frequency domain:
        plot_fictrac_fft(df, 
                        val_col, 
                        time_col, 
                        cutoff_freq=cutoff_freq, 
                        show_plots=show_plots, 
                        save_path=save_path)

        # Plot filter:
        plot_fictrac_filter(df, 
                            val_col, 
                            time_col, 
                            framerate = framerate,
                            val_label=val_label, 
                            time_label=time_label,
                            cutoff_freq = cutoff_freq, 
                            order = order, 
                            view_perc=view_perc,
                            show_plots=False, 
                            save_path=save_path)

        # Plot XY
        cm = get_all_cmocean_colours()
        plot_fictrac_XY_cmap(df,
                             cmap_col=cmap_col,
                             cmap_label=cmap_label,
                             palette=cm["thermal"],
                             show_plots=False,
                             save_path=save_path)

    # TODO: In the future I might want to generate population aggregate plots. 
    # My current plots are all for individual animals. I might want an 'agg' 
    # switch in my argparser in the future, so I can choose to output just 
    # individual animal plots, or also population aggregate plots.
    # TODO: Add histogram and ECDF population plots for speed, ang_vel, etc. 

    # Example terminal command:
    # ./analyze_fictrac.py /mnt/2TB/data_in/HK_20200317/ 2 5 delta_rotn_vector_lab_z secs_elapsed 10 2 0.01 delta\ yaw\ \(rads/frame\) time\ \(secs\) 

    
if __name__ == "__main__":
    main()