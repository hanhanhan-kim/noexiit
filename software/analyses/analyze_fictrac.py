#!/usr/bin/env python3

# TODO: Sym link my local into noexiit src? How to rid of path.insert?

"""
Process and visualize FicTrac data with helper functions. 
When run as a script, transforms .dat FicTrac files into a single concatenated 
Pandas dataframe with some additional columns. Then performs various processing 
and plotting of the FicTrac data. Includes individual animal visualizations of 
the frequency domain, low-pass Butterworth filtering, XY path with a colour map, ___. 
Includes population visualizations, such as histograms, ECDFs, and __. 
"""

import argparse
import glob
from sys import exit, path
from shutil import rmtree
from os.path import join, expanduser, exists
from os import mkdir
import re
import datetime

import yaml
import numpy as np
import pandas as pd
import scipy.interpolate as spi
import scipy.signal as sps

from bokeh.io import output_file, export_png, export_svgs, show
from bokeh.transform import linear_cmap
from bokeh.plotting import figure
from bokeh.models import ColorBar, ColumnDataSource, Span
from bokeh.layouts import gridplot
import bokeh.palettes
import colorcet as cc

import bokeh_catplot

from fourier_transform import fft, bokeh_freq_domain
path.insert(1, expanduser('~/src/cmocean-bokeh'))
from cmocean_cmaps import get_all_cmocean_colours


def get_datetime_from_logs(log, ctrl_option="online"):
    """
    Extract 't_sys' (ms) from the FicTrac .log files. 
    """
    assert (ctrl_option is "online"), \
        "This function applies only to FicTrac data acquired in real-time"
    with open (log, "r") as f:

        log_lines = f.readlines()

        datetime_list = []
        for line in log_lines:
            if "Frame captured " in line:
                # Pull out substring between t_sys and ms:
                result = re.search("t_sys: (.*?) ms", line)
                # Convert from ms to s: 
                t_sys = float(result.group(1)) / 1000
                datetime_obj = datetime.datetime.fromtimestamp(t_sys)
                datetime_list.append(datetime_obj)
        
        # FicTrac logs a t_sys before frame 0. Get rid of it:
        del datetime_list[0]

    return datetime_list


def parse_dats(root, nesting, ball_radius, ctrl_option, do_confirm=True):
    """
    Batch processes subdirectories, where each subdirectory is labelled 'fictrac'
    and has a single FicTrac .dat file and a corresponding .log file. Returns a 
    single concatenated dataframe. 
    
    The output dataframe is given proper headings, as informed by 
    the documentation on rjdmoore's FicTrac GitHub page. 

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

    ctrl_option (str): The mode with which FicTrac data (.dats and .logs) were 
        acquired. Accepts either 'online', i.e. real-time during acquisition, or 
        'offline', i.e. FicTrac was run after video acquisition.

    do_confirm (bool): If True, prompts the user to confirm the unit of the ball
        radius. If False, skips ths prompt. Default is True. 

    Returns:
    --------
    A single Pandas dataframe that concatenates all the input .dat files.
    """

    assert ctrl_option is "offline" or "online", \
        "Please provide a valid acquisition mode: either 'offline' or 'online'."

    if do_confirm is True:
        confirm = input(f"The ball_radius argument must be in mm. Confirm by inputting 'y'. Otherwise, hit any other key to quit.")
        while True:
            if confirm.lower() == "y":
                break
            else:
                exit("Re-run this function with a ball_radius that's in mm.")
    else:
        pass

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

    if ctrl_option is "online":
        datetimes_from_logs = [get_datetime_from_logs(log) for log in logs]

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
        
        # Compute times and framerate:         
        if ctrl_option is "online":
            df["datetime"] = datetimes_from_logs[i]
            df["elapsed"] = df["datetime"][1:] - df["datetime"][0]
            df["secs_elapsed"] = df.elapsed.dt.total_seconds()
            df["framerate_hz"] = 1 / df["datetime"].diff().dt.total_seconds() 

        if ctrl_option is "offline":
            # Timestamp from offline acq seems to just be elapsed ms:
            df["secs_elapsed"] = df["timestamp"] / 1000
            df["framerate_hz"] = 1 / df["secs_elapsed"].diff()
        
        df['mins_elapsed'] = df['secs_elapsed'] / 60

        # Discretize minute intervals:
        df['min_int'] = df["mins_elapsed"].apply(np.floor) + 1
        df['min_int'] = df['min_int'].astype(str).str.strip(".0")

        # Compute real-world values:
        df['X_mm'] = df['integrat_x_posn'] * ball_radius
        df['Y_mm'] = df['integrat_y_posn'] * ball_radius
        df['speed_mm_s'] = df['animal_mvmt_spd'] * df["framerate_hz"] * ball_radius

        # Assign animal number:
        df['animal'] = str(i) 

        dfs.append(df)

    concat_df = pd.concat(dfs)
        
    return concat_df


def unconcat_df(concat_df, col_name="animal"):
    """
    Splits up a concatenated dataframe according to each unique animal.
    Returns a list of datafrmaes. 

    Parameters:
    -----------
    concat_df: A Pandas dataframe
    col_name (str): A column name in 'concat_df' with which to split into smaller dataframes. 
        Default is "animal". 

    Returns:
    --------
    A list of dataframes, split up by each unique animal. 
    """

    assert (col_name in concat_df), \
        f"The column, {col_name}, is not in in the input dataframe."

    dfs_by_animal = []

    for df in concat_df[col_name].unique():
        df = concat_df.loc[concat_df[col_name]==df]
        dfs_by_animal.append(df)

    return(dfs_by_animal)


def plot_fictrac_fft(concat_df, val_cols, time_col, 
                     even=False, window=np.hanning, pad=1, 
                     cutoff_freq=None, 
                     val_labels=None, time_label=None,
                     save_path=None, show_plots=True):  
    """
    Perform a Fourier transform on FicTrac data for each animal. Generate 
    frequency domain plots for each animal. 
    Accepts one column from `concat_df`, rather than a list of columns.

    Parameters:
    ------------
    concat_df (DataFrame): Concatenated dataframe of FicTrac data generated from 
        parse_dats()

    val_cols (list): List of column names from `concat_df` to be Fourier-transformed.  

    time_col (str): Column name in `concat_df` that specifies time in SECONDS. 

    even (bool): If False, will interpolate even sampling. 

    cutoff_freq (float): x-intercept value for plotting a vertical line. 
        To be used to visualize a candidate cut-off frequency. Default is None.
    
    val_labels (list): List of labels for the plot's y-axis. If None, will 
        be a formatted version of val_cols. Default is None.

    time_label (str): Label for the plot's time-axis.

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

    dfs_by_animal = unconcat_df(concat_df, col_name="animal")

    bokeh_ps = []
    for df in dfs_by_animal: 

        assert (time_col in concat_df), \
            f"The column, {time_col}, is not in the input dataframe."
        assert ("animal" in concat_df), \
            f"The column 'animal' is not in in the input dataframe."
        
        time = list(df[str(time_col)])

        # Format axes labels:
        if time_label is None:
            time_label = time_col.replace("_", " ")
        if val_labels is None:
            val_labels = [val_col.replace("_", " ") for val_col in val_cols]

        for i, val_col, in enumerate(val_cols):

            assert (len(df[time_col] == len(df[val_col]))), \
                "time and val are different lengths! They must be the same."
            assert (val_col in concat_df), \
                f"The column, {val_col}, is not in the input dataframe."
            
            val = list(df[str(val_col)])

            # Fourier-transform:
            f = spi.interp1d(time, val)

            if even is False:
                time_interp = np.linspace(time[1], time[-1], len(time))
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

            p1.title.text = f"frequency domain of {val_labels[i]}"
            p1.title.text_font_size = "16pt"
            p1.yaxis.axis_label_text_font_size = "12pt"
            p1.border_fill_color = "#f8f5f2"
            p1.xgrid.grid_line_color = "#efe8e2"
            p1.ygrid.grid_line_color = "#efe8e2"
            p1.background_fill_color = "#f8f5f2"

            p2.yaxis.axis_label_text_font_size = "12pt"
            p2.xaxis.axis_label_text_font_size = "12pt"
            p2.border_fill_color = "#f8f5f2"
            p2.xgrid.grid_line_color = "#efe8e2"
            p2.ygrid.grid_line_color = "#efe8e2"
            p2.background_fill_color = "#f8f5f2"

            if cutoff_freq is not None:
                float(cutoff_freq)
                cutoff_line = Span(location=cutoff_freq, 
                                dimension="height", 
                                line_color="#775a42",
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


def get_filtered_fictrac(concat_df, val_cols, order, cutoff_freq, framerate=None):
    """
    Get low-pass Butterworth filtered data on offline FicTrac data. 
    Does not drop NA values.

    Parameters:
    -----------
    concat_df (DataFrame): Concatenated dataframe of FicTrac data generated from 
        parse_dats()

    val_cols (list): List of column names from `concat_df` to be filtered. 

    order (int): Order of the filter.

    cutoff_freq (float): The cutoff frequency for the filter in Hz.

    framerate (float): The mean framerate used for acquisition with FicTrac. 
        If None, will use the average frame rate as computed in the input 'concat_df'. 
        Can be overridden with a provided manual value. Default is None.

    Returns:
    --------
    A dataframe with both the filtered and raw values. 
    Filtered columns are denoted with a "filtered_" prefix.
    """

    dfs_by_animal = unconcat_df(concat_df, col_name="animal")

    filtered_dfs = []
    for df in dfs_by_animal:
        
        if framerate is None:
            framerate = np.mean(df["framerate_hz"])

        all_filtered_vals = []
        filtered_cols = []

        for val_col in val_cols:

            vals = list(df[str(val_col)])

            # Design low-pass filter:
            b, a = sps.butter(int(order), float(cutoff_freq), fs=framerate)
            # Apply filter and save:
            filtered_vals = sps.lfilter(b, a, vals)
            all_filtered_vals.append(filtered_vals)

            filtered_col = f"filtered_{val_col}"
            filtered_cols.append(filtered_col)
        
        # Convert filtered values into df:
        filtered_cols_vals = dict(zip(filtered_cols, all_filtered_vals))
        filtered_df = pd.DataFrame.from_dict(filtered_cols_vals)
        df_with_filtered = pd.concat([df, filtered_df], axis=1)
        filtered_dfs.append(df_with_filtered)
    
    return pd.concat(filtered_dfs, axis=0)


def plot_filtered_fictrac(concat_df, val_cols, time_col, 
                          order, cutoff_freq,
                          val_labels=None, time_label=None,
                          view_perc=100, 
                          save_path=None, show_plots=True):
    """
    Apply a low-pass Butterworth filter on offline FicTrac data for plotting. 

    Parameters:
    -----------
    concat_df (DataFrame): Concatenated and filtered dataframe of FicTrac data generated 
        from parse_dats(). 

    val_cols (list): List of column names from `concat_df` to be Fourier-transformed. 

    time_col (str): Column name from `concat_df` that specifies time. 

    order (int): Order of the filter.

    cutoff_freq (float): The cutoff frequency for the filter in Hz.

    val_labels (list): List of labels for the plot's y-axis. If None, will 
        be a formatted version of cmap_cols. Default is None.

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
    
    assert (0 <= view_perc <= 100), \
        f"The view percentage, {view_perc}, must be between 0 and 100."
    
    filtered_concat_df = get_filtered_fictrac(concat_df, val_cols, order, cutoff_freq).dropna()
    dfs_by_animal = unconcat_df(filtered_concat_df, col_name="animal")

    bokeh_ps = []
    for df in dfs_by_animal:
        
        # Format axes labels:
        if time_label is None:
            time_label = time_col.replace("_", " ")
        if val_labels is None:
            val_labels = [val_col.replace("_", " ") for val_col in val_cols]
        
        # View the first _% of the data:
        domain = int(view_perc/100 * len(df[time_col]))

        for i, val_col in enumerate(val_cols):
            assert (len(df[time_col] == len(df[val_col]))), \
                "time and vals are different lengths! They must be the same."
            assert (time_col in concat_df), \
                f"The column, {time_col}, is not in the input dataframe."
            assert (val_col in concat_df), \
                f"The column, {val_col}, is not in the input dataframe."
            assert ("animal" in concat_df), \
                f"The column 'animal' is not in in the input dataframe."
            assert (f"filtered_{val_col}" in filtered_concat_df), \
                f"The column, filtered_{val_col} is not in the filtered dataframe."
            
            # Plot:
            p = figure(
                width=1600,
                height=500,
                x_axis_label=time_label,
                y_axis_label=val_labels[i] 
            )
            p.line(
                x=df[time_col][:domain],
                y=df[val_col][:domain],
                color=bokeh.palettes.brewer["Paired"][3][0],
                legend_label="raw"
            )
            p.line(
                x=df[time_col][:domain],
                y=df[f"filtered_{val_col}"][:domain],
                color=bokeh.palettes.brewer["Paired"][3][1],
                legend_label="filtered"
            )
            p.title.text = f"first {view_perc}% with butterworth filter: cutoff = {cutoff_freq} Hz, order = {order}"
            p.title.text_font_size = "14pt"
            p.yaxis.axis_label_text_font_size = "12pt"
            p.yaxis.axis_label_text_font_size = "12pt"
            p.xaxis.axis_label_text_font_size = "12pt"
            p.legend.background_fill_color = "#f8f5f2"
            p.border_fill_color = "#f8f5f2"
            p.xgrid.grid_line_color = "#efe8e2"
            p.ygrid.grid_line_color = "#efe8e2"
            p.background_fill_color = "#f8f5f2"
            
            # Output:
            if save_path is not None:
                filename = join(save_path, f"filtered_{val_col}")
                
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


def plot_fictrac_XY_cmap(concat_df, cmap_cols, low=0, high_percentile=95, respective=False, 
                         cmap_labels=None,
                         order=2, cutoff_freq=4, 
                         palette = cc.CET_L16, size=2.5, alpha=0.3, 
                         show_start=False, 
                         save_path=None, show_plots=True):
    """
    Plot XY FicTrac coordinates of the animal with a linear colourmap for 
    a FicTrac variable of choice. 
    
    Parameters:
    -----------
    concat_df (DataFrame): Concatenated dataframe of FicTrac data generated from 
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
        the 'high_percentile' value computed from the population, i.e. from `concat_df`. 
        Default is False. 

    cmap_cols (list): List of column names from `concat_df` to be colour-mapped. 

    cmap_labels (list): List of labels for the plots' colourbars. If None, will 
        be a formatted version of cmap_cols. Default is None.

    order (int): Order of the filter.

    cutoff_freq (float): The cutoff frequency for the filter in Hz.

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
    assert ("X_mm" in concat_df), \
        f"The column, 'X_mm', is not in the input dataframe."
    assert ("Y_mm" in concat_df), \
        f"The column, 'Y_mm', is not in the input dataframe."
    assert ("animal" in concat_df), \
            f"The column 'animal' is not in in the input dataframe."
    
    filtered_concat_df = get_filtered_fictrac(concat_df, cmap_cols, 
                                              order=order, cutoff_freq=cutoff_freq).dropna()
    dfs_by_animal = unconcat_df(filtered_concat_df, col_name="animal")

    bokeh_ps = []
    for df in dfs_by_animal:
        
        # Format axes labels:
        if cmap_labels is None:
            cmap_labels = [cmap_col.replace("_", " ") for cmap_col in cmap_cols]

        for i, cmap_col in enumerate(cmap_cols):
            
            assert (cmap_col in concat_df), \
                f"The column, {cmap_col}, is not in the input dataframe."
            assert (f"filtered_{cmap_col}" in filtered_concat_df), \
                f"The column, filtered_{cmap_col} is not in the filtered dataframe."
            assert (len(df["X_mm"] == len(df["Y_mm"]))), \
                "X_mm and Y_mm are different lengths! They must be the same."

            # Use only the FILTERED cmap_col:
            cmap_col = f"filtered_{cmap_col}"

            if respective is False:
                # Normalize colourmap range to animal population:
                high = np.percentile(filtered_concat_df[cmap_col], high_percentile)
            elif respective is True:
                # Individual animal sets its own colourmap range:
                high = np.percentile(df[cmap_col], high_percentile)
            
            source = ColumnDataSource(df)

            mapper = linear_cmap(field_name=cmap_col, 
                                palette=palette, 
                                low=low, 
                                high=high)
            
            p = figure(width=800,
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

            # TODO: also change colorbar labels so max has =< symbol
            color_bar = ColorBar(color_mapper=mapper['transform'], 
                                 title=cmap_labels[i],
                                 title_text_font_size="7pt",
                                 width=10,
                                 background_fill_color="#f8f5f2",
                                 location=(0,0))

            p.add_layout(color_bar, "right")

            p.title.text_font_size = "14pt"
            p.xaxis.axis_label_text_font_size = '10pt'
            p.yaxis.axis_label_text_font_size = '10pt'
            p.border_fill_color = "#f8f5f2"
            p.xgrid.grid_line_color = "#efe8e2"
            p.ygrid.grid_line_color = "#efe8e2"
            p.background_fill_color = "#f8f5f2"

            bokeh_ps.append(p)

            # Output:
            if save_path is not None:
                filename = save_path + f"fictrac_XY_{cmap_col}"
                
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


def plot_fictrac_histograms(concat_df, cols=None, labels=None, 
                            cutoff_percentile=95,
                            save_path=None, show_plots=True):
    """
    Generate histograms for multiple FicTrac kinematic variables. 

    Parameters:
    -----------
    concat_df (DataFrame): Concatenated dataframe of FicTrac data generated from 
        parse_dats()

    cols (list): List of strings specifying column names in 'concat_df'. If None, 
        uses default columns that specify real-world and 'lab' kinematic measurements.
        Otherwise, will use both input arguments and the default columns. Default is None.

    labels (list): List of strings specifying the labels for the histograms' x-axes.
        Its order must correspond to 'cols'. 

    cutoff_percentile (float): Specifies the percentile of the AGGREGATE population data. 
        Plots a line at this value. Default is 95th percentile. 
        
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
    assert ("animal" in concat_df), \
            f"The column 'animal' is not in in the input dataframe."
    
    all_cols = list(concat_df.columns)
    
    banned_substrings = ["integrat_x_posn", 
                         "integrat_y_posn", 
                         "X_mm", 
                         "Y_mm", 
                         "seq_cntr", 
                         "timestamp", 
                         "cam", 
                         "frame", 
                         "elapse", 
                         "datetime",
                         "framerate",
                         "min",
                         "animal",
                         "__"] 
    banned_cols = []
    for col in all_cols:
        for substring in banned_substrings:
            if substring in col:
                banned_cols.append(col)
                break

    ok_cols = [col for col in all_cols if col not in banned_cols]
    
    if cols is None:
        cols = ok_cols
    else:
        cols = ok_cols + cols 
        for col in cols:
            assert (col in concat_df), f"The column, {col}, is not in the input dataframe."
    
    if labels is None:
        labels = [col.replace("_", " ") for col in cols] 
    
    bokeh_ps = []
    for i, col in enumerate(cols):
        p = bokeh_catplot.histogram(data=concat_df,
                                    cats=['animal'],
                                    val=col,
                                    density=True,
                                    width=1000,
                                    height=500)
        
        cutoff_line = Span(location=np.percentile(concat_df[col], cutoff_percentile), 
                           dimension="height", 
                           # line_color="#e41a1c",
                           line_color = "#775a42",
                           line_dash="dashed",
                           line_width=2)
        
        p.legend.location = "top_right"
        p.legend.title = "animal ID"
        p.legend.background_fill_color = "#f8f5f2"
        p.border_fill_color = "#f8f5f2"
        p.xgrid.grid_line_color = "#efe8e2"
        p.ygrid.grid_line_color = "#efe8e2"
        p.background_fill_color = "#f8f5f2"
        p.title.text = f" with aggregate {cutoff_percentile}% mark"
        p.xaxis.axis_label = labels[i]
        p.xaxis.axis_label_text_font_size = "12pt"
        p.yaxis.axis_label_text_font_size = "12pt"
        p.add_layout(cutoff_line)
            
        # Output:
        if save_path is not None:
            filename = save_path + f"fictrac_histogram_by_animal_{col}"

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


def plot_fictrac_ecdfs(concat_df, cols=None, labels=None, 
                       cutoff_percentile=95, 
                       save_path=None, show_plots=True):
    """
    Generate ECDFs for multiple FicTrac kinematic variables. 

    Parameters:
    -----------
    concat_df (DataFrame): Concatenated dataframe of FicTrac data generated from 
        parse_dats()

    cols (list): List of strings specifying column names in 'concat_df'. If None, 
        uses default columns that specify real-world and 'lab' kinematic measurements.
        Otherwise, will use both input arguments and the default columns. Default is None.

    labels (list): List of strings specifying the labels for the ECDFs' x-axes.
        Its order must correspond to 'cols'. 

    cutoff_percentile (float): Specifies the percentile of the AGGREGATE population data. 
        Plots a line at this value. Default is 95th percentile. 
    
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
    assert ("animal" in concat_df), \
            f"The column 'animal' is not in in the input dataframe."
    
    all_cols = list(concat_df.columns)
        
    banned_substrings = ["integrat_x_posn", 
                         "integrat_y_posn", 
                         "X_mm", 
                         "Y_mm", 
                         "seq_cntr", 
                         "timestamp", 
                         "cam", 
                         "frame", 
                         "elapse",
                         "datetime",
                         "framerate", 
                         "min",
                         "animal",
                         "__"] 
    banned_cols = []
    for col in all_cols:
        for substring in banned_substrings:
            if substring in col:
                banned_cols.append(col)
                break

    ok_cols = [col for col in all_cols if col not in banned_cols]
    
    if cols is None:
        cols = ok_cols
    else:
        cols = ok_cols + cols 
        for col in cols:
            assert (col in concat_df), f"The column, {col}, is not in the input dataframe"
    
    if labels is None:
        labels = [col.replace("_", " ") for col in cols] 
    
    bokeh_ps = []
    for i, col in enumerate(cols):
        p = bokeh_catplot.ecdf(data=concat_df,
                               cats=["animal"],
                               val=col,
                               kind="colored",
                               width=1000,
                               height=500)
        
        cutoff_line = Span(location=np.percentile(concat_df[col], cutoff_percentile), 
                           dimension="height", 
                           line_color="#775a42",
                           line_dash="dashed",
                           line_width=2)
        
        p.legend.location = 'top_right'
        p.legend.title = "animal ID"
        p.legend.background_fill_color = "#f8f5f2"
        p.border_fill_color = "#f8f5f2"
        p.xgrid.grid_line_color = "#efe8e2"
        p.ygrid.grid_line_color = "#efe8e2"
        p.background_fill_color = "#f8f5f2"
        p.title.text = f" with aggregate {cutoff_percentile}% mark"
        p.xaxis.axis_label = labels[i]
        p.xaxis.axis_label_text_font_size = "12pt"
        p.yaxis.axis_label_text_font_size = "12pt"
        p.add_layout(cutoff_line)
        
        # Output:
        if save_path is not None:
            filename = save_path + f"fictrac_ecdfs_{col}"
            
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
    
    # TODO: Move this documentation to a README.md in software/
    # parser = argparse.ArgumentParser(description = __doc__)
    # parser.add_argument("ctrl_option", 
    #     help="The mode with which FicTrac data (.dats and .logs) were acquired. \
    #         Accepts either 'online', i.e. real-time during acquisition, or \
    #         'offline', i.e. FicTrac was run after video acquisition.")
    # parser.add_argument("root",
    #     help="Absolute path to the root directory. I.e. the outermost \
    #         folder that houses the FicTrac files.\
    #         E.g. /mnt/2TB/data_in/test/")
    # parser.add_argument("nesting", type=int,
    #     help="Specifies the number of folders that are nested from \
    #         the root directory. I.e. The number of folders between root \
    #         and the 'fictrac' subdirectory that houses the .dat and .log files. \
    #         This subdirectory MUST be called 'fictrac'.")
    # parser.add_argument("ball_radius", type=float,
    #     help="The radius of the ball used with the insect-on-a-ball tracking rig. \
    #         Must be in mm.")
    # # parser.add_argument("val_cols", 
    # #     help="List of column names of the Pandas dataframe to be used as the \
    # #         dependent variables for analyses.")
    # parser.add_argument("time_col",
    #     help="Column name of the Pandas dataframe specifying the time.")
    # parser.add_argument("cmap_col",
    #     help="Column name of the Pandas dataframe specifying the variable to be \
    #         colour-mapped.")
    # parser.add_argument("cutoff_freq", type=float,
    #     help="Cutoff frequency to be used for filtering the FicTrac data.")
    # parser.add_argument("order", type=int,
    #     help="Order of the filter.")
    # parser.add_argument("view_percent", type=float,
    #     help="Specifies how much of the filtered data to plot as an initial \
    #         percentage. Useful for assessing the effectieness of the filter over \
    #         longer timecourses. Default is set to 1, i.e. plot the data over the \
    #         entire timecourse. Must be a value between 0 and 100.")
    # parser.add_argument("percentile_max_clamp", type=float,
    #     help="Specifies the percentile at which to clamp the max depicted \
    #         colourmap values. Plots a span at this value for the population \
    #         histograms and ECDFs.")
    # parser.add_argument("alpha_cmap", type=float,
    #     help="Specifies the transparency of each datum on the XY colourmap plots. \
    #         Must be between 0 and 1, inclusive.")

    # parser.add_argument("val_labels", nargs="?", default=None,
    #     help="list of y-axis label of the generated plots. Default is a formatted \
    #         version of val_cols")
    # parser.add_argument("time_label", nargs="?", default=None,
    #     help="time-axis label of the generated plots. Default is a formatted \
    #         time_col")
    # parser.add_argument("cmap_label", nargs="?", default=None,
    #     help="label of the colour map legend")
    # parser.add_argument("framerate", nargs="?", default=None, type=float,
    #     help="The mean framerate used for acquisition with FicTrac. \
    #         If None, will compute the average framerate. Can be overridden with a \
    #         provided manual value. Default is None.") 
    
    # parser.add_argument("-ns", "--no_save", action="store_true", default=False,
    #     help="If enabled, does not save the plots. By default, saves plots.")
    # parser.add_argument("-sh", "--show", action="store_true", default=False,
    #     help="If enabled, shows the plots. By default, does not show the plots.")
    # args = parser.parse_args()

    # root = args.root
    # nesting = args.nesting 
    # ctrl_option = args.ctrl_option
    # # TODO: ctrl_option bug; won't accept as argparse arg
    # ctrl_option = "online"
    # ball_radius = args.ball_radius # mm

    # # val_cols = args.val_cols
    # # TODO: hard code for now for testing:
    # val_cols = ["delta_rotn_vector_lab_y", "speed_mm_s"]

    # val_labels = args.val_labels
    # time_col = args.time_col
    # time_label = args.time_label
    # cmap_col = args.cmap_col
    # cmap_label = args.cmap_label 
    # cutoff_freq = args.cutoff_freq
    # framerate = args.framerate 
    # order = args.order
    # view_perc = args.view_percent
    # percentile_max_clamp = args.percentile_max_clamp
    # alpha_cmap = args.alpha_cmap

    # no_save = args.no_save
    # show_plots = args.show 


    with open("fictrac_analyses_params.yaml") as f:

        params = yaml.load(f, Loader=yaml.FullLoader)
        # print(params)

    root = params["root"]
    nesting = params["nesting"]
    ctrl_option = params["ctrl_option"]
    # TODO: FIX!
    ctrl_option = "online"
    ball_radius = params["ball_radius"]

    val_cols = params["val_cols"]
    val_labels = params["val_labels"]

    time_col = params["time_col"]
    time_label = params["time_label"]

    cutoff_freq = params["cutoff_freq"]
    order = params["order"]
    framerate = params["framerate"]

    view_perc = params["view_perc"]

    cmap_cols = params["cmap_cols"]
    cmap_labels = params["cmap_labels"]
    alpha_cmap = params["alpha_cmap"]
    percentile_max_clamp = params["percentile_max_clamp"]

    no_save = params["no_save"]
    show_plots = params["show_plots"]

    # Parse FicTrac inputs:
    concat_df = parse_dats(root, nesting, ball_radius, ctrl_option, do_confirm=False).dropna()
    
    # Unconcatenate the concatenated df:
    dfs_by_animal = unconcat_df(concat_df, col_name="animal")

    # Save each individual animal bokeh plot to its respective animal folder. 
    folders = sorted(glob.glob(join(root, nesting * "*/", "fictrac/")))

    # Generate individual animal plots:
    save_paths = []
    for df, folder in zip(dfs_by_animal, folders):
        
        save_path = join(folder, "plots/")
        save_paths.append(save_path)
        
        if exists(save_path):
            rmtree(save_path)
        mkdir(save_path)

        if no_save is True:
            save_path = None
        
        print(f"Generating individual plots for {folder} ...")

        # Plot FFT frequency domain:
        plot_fictrac_fft(df, 
                        val_cols=val_cols, 
                        time_col=time_col, 
                        val_labels=val_labels,
                        time_label=time_label,
                        cutoff_freq=cutoff_freq, 
                        save_path=save_path,
                        show_plots=show_plots) 

        # Plot filtered:
        plot_filtered_fictrac(df, 
                              val_cols=val_cols, 
                              time_col=time_col, 
                              val_labels=val_labels, 
                              time_label=time_label,
                              cutoff_freq=cutoff_freq, 
                              order=order, 
                              view_perc=view_perc,
                              save_path=save_path,
                              show_plots=show_plots)

        # Plot XY
        cm = get_all_cmocean_colours()
        plot_fictrac_XY_cmap(df,
                             cmap_cols=cmap_cols,
                             high_percentile=percentile_max_clamp,
                             cmap_labels=cmap_labels,
                             palette=cm["thermal"],
                             alpha=alpha_cmap,
                             save_path=save_path,
                             show_plots=show_plots)

    # Generate population plots:
    print("Generating population plots ...")
    save_path_popns = join(root, "popn_plots/")
    if exists(save_path_popns):
        rmtree(save_path_popns)
    mkdir(save_path_popns)
    subdirs = ["histograms/", "ecdfs/"]
    [mkdir(join(root, "popn_plots/", subdir)) for subdir in subdirs]

    save_path_histos = join(root, "popn_plots/", "histograms/")
    save_path_ecdfs = join(root, "popn_plots/", "ecdfs/")

    # Plot histograms:
    print("Generating histograms ...")
    plot_fictrac_histograms(concat_df, 
                            cutoff_percentile=percentile_max_clamp,
                            save_path=save_path_histos, 
                            show_plots=False)

    # Plot ECDFs:
    print("Generating ECDFs ...")
    plot_fictrac_ecdfs(concat_df,
                       cutoff_percentile=percentile_max_clamp,
                       save_path=save_path_ecdfs, 
                       show_plots=False)
    

if __name__ == "__main__":
    main()