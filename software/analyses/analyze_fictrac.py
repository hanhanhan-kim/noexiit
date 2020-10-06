#!/usr/bin/env python3

# TODO: Sym link my local into noexiit src? How to rid of path.insert?

"""
Process and visualize FicTrac data with helper functions. 
When run as a script, transforms .dat FicTrac files into a single concatenated 
Pandas dataframe with some additional columns. Then performs various processing 
and plotting of the FicTrac data. Includes individual visualizations of 
the frequency domain, low-pass Butterworth filtering, XY path with a colour map, ___. 
Includes population visualizations, such as histograms, ECDFs, and __. 
"""

import argparse
import glob
from sys import exit, path
from shutil import rmtree
from os.path import join, expanduser, exists, commonpath
from pathlib import Path
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
from bokeh.models import ColorBar, ColumnDataSource, Span, BoxAnnotation
from bokeh.layouts import gridplot
import bokeh.palettes
import colorcet as cc

import iqplot

from fourier_transform import fft, bokeh_freq_domain
path.insert(1, expanduser('~/src/cmocean-bokeh'))
from cmocean_cmaps import get_all_cmocean_colours


def get_datetime_from_logs(log, acq_mode="online"):

    """
    Extract 't_sys' (ms) from the FicTrac .log files. 
    """

    assert (acq_mode == "online"), \
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


def parse_dats(root, ball_radius, acq_mode, do_confirm=True):

    """
    Batch processes subdirectories, where each subdirectory is labelled 'fictrac'
    and MUST have a single FicTrac .dat file and a corresponding .log file. 
    Returns a single concatenated dataframe. 
    
    The output dataframe is given proper headings, as informed by 
    the documentation on rjdmoore's FicTrac GitHub page. 

    Elapsed time is converted into seconds and minutes, and the integrated 
    X and Y positions are converted to real-world values, by multiplying them 
    against the ball radius. 
    
    Parameters:
    -----------
    root (str): Absolute path to the root directory. I.e. the outermost 
        folder that houses the FicTrac .avi files

    ball_radius (float): The radius of the ball (mm) the insect was on. 
        Used to compute the real-world values in mm.  

    acq_mode (str): The mode with which FicTrac data (.dats and .logs) were 
        acquired. Accepts either 'online', i.e. real-time during acquisition, or 
        'offline', i.e. FicTrac was run after video acquisition.

    do_confirm (bool): If True, prompts the user to confirm the unit of the ball
        radius. If False, skips ths prompt. Default is True. 

    Returns:
    --------
    A list of dataframes. 
    """

    assert acq_mode == "offline" or "online", \
        "Please provide a valid acquisition mode: either 'offline' or 'online'."

    if do_confirm == True:
        confirm = input(f"The ball_radius argument must be in mm. Confirm by inputting 'y'. Otherwise, hit any other key to quit.")
        while True:
            if confirm.lower() == "y":
                break
            else:
                exit("Re-run this function with a ball_radius that's in mm.")
    else:
        pass

    logs = sorted([path.absolute() for path in Path(root).rglob("*.log")])
    dats = sorted([path.absolute() for path in Path(root).rglob("*.dat")])
    
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

    if acq_mode == "online":
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
        if acq_mode == "online":
            df["datetime"] = datetimes_from_logs[i]
            df["elapsed"] = df["datetime"][1:] - df["datetime"][0]
            df["secs_elapsed"] = df.elapsed.dt.total_seconds()
            df["framerate_hz"] = 1 / df["datetime"].diff().dt.total_seconds() 

        if acq_mode == "offline":
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

        # Assign ID number:
        df['ID'] = str(i) 

        dfs.append(df)

    return dfs


# TODO: Move to a more general file:
def unconcat(concat_df, col_name="ID"):

    """
    Splits up a concatenated dataframe according to each unique `col_name`.
    Returns a list of datafrmaes. 

    Parameters:
    -----------
    concat_df: A Pandas dataframe
    col_name (str): A column name in 'concat_df' with which to split into smaller dataframes. 
        Default is "ID". 

    Returns:
    --------
    A list of dataframes, split up by each `col_name`. 
    """

    assert (col_name in concat_df), \
        f"The column, {col_name}, is not in in the input dataframe."

    dfs_by_ID = []

    for df in concat_df[col_name].unique():
        df = concat_df.loc[concat_df[col_name]==df]
        dfs_by_ID.append(df)

    return(dfs_by_ID)


# TODO: Move to a more general file:
def flatten_list(list_of_lists):
    
    """
    Flatten a list of lists into a list.

    Parameters:
    -----------
    list_of_lists: A list of lists

    Returns:
    --------
    A list.
    """
    
    # Reach into each inner list and append into a new list: 
    flat_list = [item for inner_list in list_of_lists for item in inner_list]

    return flat_list


# TODO: Move to a more general file:
def read_csv_and_add_metadata(paths):

    """
    Reads `.csv` data into a dataframe, then adds metadata from each file's path to the 
    dataframe. Assumes that there exists somewhere in the path, a directory structure 
    that goes 'date -> animal -> trial', where 'trial' holds the `.csv` data. 
    
    Parameters:
    ------------
    paths: A list of paths

    Returns:
    ---------
    A list of dataframes
    """
    
    common_path = commonpath(paths)
    
    dfs = []
    for path in paths:
        
        new_path = path.replace(f"{common_path}/", "")
        date = new_path.split("/")[0]
        animal = new_path.split("/")[1]
        trial = new_path.split("/")[2]
        
        df = pd.read_csv(path)
        df["date"] = date
        df["animal"] = animal
        df["trial"] = trial
        
        dfs.append(df)
        
    return(dfs)


# TODO: Move this to a more general file:
def search_for_paths(basepath, group_members, glob_ending="*/fictrac"):

    """
    Search with a list of subdirectories, to get a list of paths, 
    where each path ends in `glob_ending`. 

    Parameters:
    -----------
    basepath: Longest common path shared by each glob search return. 
    group_members: List of group members. Each element must be a substring
        in the path to the `glob_ending` result. 
    glob_ending: A Unix-style path ending. Supports '*' wildcards. 

    Returns:
    --------
    A list of paths
    """

    # TODO: Fix--currently assumes that group_member IMMEDIATELY follows basepath, 
    # as seen in the join() below. Need to make it more general. 
    
    new_paths = [str(path.absolute()) 
                for group_member in group_members 
                for path in Path(join(basepath, group_member)).rglob(glob_ending)]
    
    return sorted(new_paths)


def parse_dats_by_group(basepath, group_members, 
                        ball_radius, acq_mode, do_confirm):
    
    """
    Parse `.dat` files by a group of manually specified group members. 
    Wraps the `parse_dats()` function.

    Parameters:
    -----------
    basepath: Longest common path shared by each element in `group_members`. 
    group_members: List of group members. Each element must be a substring 
        in the path to the FicTrac `.dat` file. 

    Returns:
    --------
    A list of dataframes
    """

    # assert ("ID" in df), \
    #     "The dataframe must have a column called `ID`"
    # TODO: Checks sorting

    paths = search_for_paths(basepath, group_members)
    dfs = [parse_dats(path, ball_radius, acq_mode, do_confirm) for path in paths]
    
    return flatten_list(dfs)


# TODO: Move to a more general file:
def add_metadata_to_dfs(paths, dfs):

    """
    Adds metadata from each file's path to the dataframe. Assumes that there exists 
    somewhere in the path, a directory structure that goes 'date -> animal -> trial', where
    'trial' holds the data, e.g. `.dat` or `.csv`. 
    
    Parameters:
    -------------
    paths: list of paths
    dfs: list of dataframes

    Returns:
    ---------
    A list of dataframes
    """

    # TODO: How to add a check for "date -> animal -> trial -> .dat" structure? 

    common_path = commonpath(paths)
    
    dfs_with_metadata = []
    for path, df in zip(paths, dfs):
        
        assert len(paths) == len(dfs), "Lengths of `paths` and `dfs` are unequal"
        # TODO: Add check to see if `paths` and `dfs` are sorted in the same way. 
        
        new_path = path.replace(f"{common_path}/", "")
        date = new_path.split("/")[0]
        animal = new_path.split("/")[1]
        trial = new_path.split("/")[2]
        
        df["date"] = date
        df["animal"] = animal
        df["trial"] = trial
        
        dfs_with_metadata.append(df)
        
    return(dfs_with_metadata)


# TODO: Move to a more general file:
def regenerate_IDs(df, group_by=["date", "animal", "trial"]):

    """
    Regenerate unique animal IDs according to some groupby criteria. 
    Useful for when a previous function sets IDs according to 
    some intermediate groupby structure. 
    
    Parameters:
    ------------
    df: dataframe
    group_by: a list of columns in `df` with which to perform the groupby
    
    Returns:
    ---------
    A dataframe
    """

    # TODO: Check that elements of group_by are columns in the dataframe

    # Assign unique group IDs:
    df["ID"] = (df.groupby(group_by).cumcount()==0).astype(int)
    df["ID"] = df["ID"].cumsum()
    df["ID"] = df["ID"].apply(str)
    
    return df


# TODO: Move to a more general file:
def curate_by_date_animal(df, included):

    """
    Curate a dataframe according to values in its `date` and `animal` columns.

    Parameters:
    ------------
    df: the dataframe to be curated
    included: list of (<date>, <animal>) tuples to be included in the groupby
    
    Returns:
    ---------
    The curated dataframe and the number of animals after curation
    """

    assert ("date" in df), "The dataframe must have a column called 'date'"
    assert ("animal" in df), "The dataframe must have a column called 'animal'"
    
    # groupby has 3 keys:
    grouped = df.groupby(["date", "animal", "trial"])
    
    # Apply curation to generate a list of dataframes:
    groups = []
    for name, group in grouped:
        # Slice based on first 2 keys, date and animal, only:
        if name[:2] in included:
            groups.append(group)
            
    # Concatenate the dataframes back together:
    concat_curated_df = pd.concat(groups)
    
    # Get n animals:
    n_animals = len(concat_curated_df.groupby(["date", "animal"]))
    
    return(concat_curated_df, n_animals)


def process_dats(basepath, group_members, 
                 ball_radius, acq_mode, do_confirm, 
                 cols_to_filter, order, cutoff_freq): 
    
    """
    Process a group of `.dat`s. Reads and parses `.dat`s, adds metadata 
    from corresponding paths, filters specified columns, concatenates 
    dataframes, and regenerates IDs.

    Parameters:
    -----------
    basepath
    group_members
    ball_radius
    acq_mode
    do_confirm
    cols_to_filter: A list of columns to filter

    Returns:
    --------
    A single concatenated dataframe.        
    """

    paths = search_for_paths(basepath, group_members)
    dfs = parse_dats_by_group(basepath, group_members, ball_radius, acq_mode, do_confirm)
    dfs = add_metadata_to_dfs(paths, dfs)
    # If the first row of a column to be filtered is NaN, all subsequent rows are NaNs:
    dfs = [df.dropna() for df in dfs]
    dfs = [filter(df, cols_to_filter, order, cutoff_freq) for df in dfs]
    # Filtering results in NaNs in the first row of each dataframe:
    dfs = [df.dropna() for df in dfs] 
    df = regenerate_IDs(pd.concat(dfs))

    return df


# TODO: Move to a more general file:
def baseline_subtract(df, baseline_end, time_col, val_col):
    
    # TODO: Update val_col to val_cols for multiple vals:
    
    """
    Computes a mean baseline value for a column in the dataframe 
    and subtracts that value from the data.
    
    Parameters:
    -----------
    df: A dataframe
    baseline_end (fl): The time at which the baseline period ends.
    time_col:  
    val_col:
    
    Returns:
    --------
    A dataframe
    """
    
    # Compute a mean value as the baseline:
    baseline = np.mean(df.loc[df[time_col] < baseline_end][val_col])

    # Subtract baseline from val_col:
    df[val_col] = df[val_col] - baseline
    
    return df


# TODO: Move to a more general file:
def compute_z_from_subseries(series, subseries):
    
    """
    From timeseries data, compute the z-score based on a mu and sigma 
    that are derived from a subset of the timeseries (a subseries), 
    e.g. from a pre-stimulus period. 

    Parameters:
    -----------
    
    
    Returns:
    --------
    A z-score for each datapoint in the entire timeseries.
    """
    
    mu = np.mean(subseries)
    sigma = np.std(subseries) 
    
    return ([(val - mu) / sigma for val in series])


# TODO: Move to a more general file:
def compute_z_from_subdf(df, val_col, time_col, 
                         subseries_end, subseries_start=0):
    """
    From a timeseries dataframe, compute the z-score based on a mu 
    and sigma that are derived from a subset of the timeseries (a 
    sub-dataframe), e.g. from a pre-stimulus period. 

    Parameters:
    -----------

    
    Returns:
    --------
    A z-score for each datapoint in the entire timeseries dataframe.
    """
    
    # Separate out the features:
    x = df[val_col]

    # Standardize the features:
    start = df[time_col] > subseries_start
    end = df[time_col] < subseries_end
    
    x_sub = df.loc[start & end][val_col]
    x = compute_z_from_subseries(x, x_sub)

    # Add the feature back to the dataframe:
    # TODO: Remove (sth) before adding (z-score)
    df[f"{val_col} (z-score)"] = x
    
    return df


# TODO: Move to a more general file:
# Themes for colouring plots:
themes = {"beige":{"dark_hue":"#efe8e2", "light_hue":"#f8f5f2"}}


# TODO: Move to a more general file:
def load_plot_theme(p, theme=None, has_legend=False):
    
    """
    Load theme colours into a Bokeh plotting object. 

    Parameters:
    -----------
    p: A Bokeh plotting object
    
    Returns:
    --------
    `p` with coloured attributes. 
    """
    
    assert (theme in themes or theme is None), \
        f"{theme} is neither None nor a valid key in `themes`"

    if theme is not None:

        theme_colours = themes[theme]
            
        dark_hue = theme_colours["dark_hue"]
        light_hue = theme_colours["light_hue"]

        p.border_fill_color = light_hue
        p.xgrid.grid_line_color = dark_hue
        p.ygrid.grid_line_color = dark_hue
        p.background_fill_color = light_hue 

        if has_legend == True:
            p.legend.background_fill_color = light_hue
        else:
            pass

        return p
    
    else:
        pass


def plot_fft(df, val_cols, time_col, 
             is_evenly_sampled=False, window=np.hanning, pad=1, 
             cutoff_freq=None, 
             val_labels=None, time_label=None,
             theme=None,
             save_path_to=None, show_plots=True):  

    """
    Perform a Fourier transform on FicTrac data for each ID. Generate 
    power spectrum plots for each value in `val_cols`. 
    Accepts one column from `df`, rather than a list of columns.

    Parameters:
    ------------
    df (DataFrame): Dataframe of FicTrac data generated from parse_dats()

    val_cols (list): List of column names from `df` to be Fourier-transformed.  

    time_col (str): Column name in `df` that specifies time in SECONDS. 

    is_evenly_sampled (bool): If False, will interpolate even sampling. 

    cutoff_freq (float): x-intercept value for plotting a vertical line. 
        To be used to visualize a candidate cut-off frequency. Default is None.
    
    val_labels (list): List of labels for the plot's y-axis. If None, will 
        be a formatted version of val_cols. Default is None.

    time_label (str): Label for the plot's time-axis.

    theme (str or None): A pre-defined colour theme for plotting. If None,
        does not apply a theme. Default is None.

    save_path_to (str): Absolute path to which to save the plots as .png files. 
        If None, will not save the plots. Default is None. 

    show_plots (bool): If True, will show plots, but will not output Bokeh plotting 
        objects. If False, will not show plots, but will output Bokeh plotting objects. 
        If both save and show_plots are True, .html plots will be generated, in addition 
        to the .png plots. Default is True.

    Returns:
    ---------
    if show_plots is True: will show plots instead of outputting bokeh.plotting.figure object.
    if show_plots is False: will output bokeh.plotting.figure objects, instead of showing plots.
    if save_path_to is not None: will save .png plots to specified path. 
    if save_path_to is None: will not save plots.
    """
    
    if not ('sec' in time_col or '(s)' in time_col):
        safe_secs = input(f"The substrings 'sec' or '(s)' was not detected in the 'time_col' variable, {time_col}. The units of the values in {time_col} MUST be in seconds. If the units are in seconds, please input 'y'. Otherwise input anything else to exit.")
        while True:
            if safe_secs.lower() == "y":
                break
            else:
                exit("Re-run this function with a 'time_col' whose units are secs.")

    assert (time_col in df), f"The column, {time_col}, is not in the input dataframe."
    assert ("ID" in df), "The column 'ID' is not in in the input dataframe."
    
    time = list(df[str(time_col)])

    # Format axes labels:
    if time_label == None:
        time_label = time_col.replace("_", " ")
    if val_labels == None:
        val_labels = [val_col.replace("_", " ") for val_col in val_cols]

    plots = []
    for i, val_col, in enumerate(val_cols):

        assert (len(df[time_col] == len(df[val_col]))), \
            "time and val are different lengths! They must be the same."
        assert (val_col in df), \
            f"The column, {val_col}, is not in the input dataframe."
        
        val = list(df[str(val_col)])

        # Fourier-transform:
        f = spi.interp1d(time, val)

        if is_evenly_sampled == False:
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

        p1.title.text = f"power spectrum of {val_labels[i]}"
        p1.title.text_font_size = "16pt"
        p1.yaxis.axis_label_text_font_size = "12pt"
        load_plot_theme(p1, theme=theme)

        p2.yaxis.axis_label_text_font_size = "12pt"
        p2.xaxis.axis_label_text_font_size = "12pt"
        load_plot_theme(p2, theme=theme)

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
        if save_path_to is not None:
            filename = save_path_to + f"fictrac_freqs"

            # Bokeh does not atm support gridplot svg exports
            export_png(p, filename = filename + ".png")
            output_file(filename = filename + ".html", 
                        title=f"fictrac_freqs")

        if show_plots == True:
            show(p)

        # In case show_plots is False:
        plots.append(p)

    if show_plots == False:
        return plots


# TODO: Move to a more general file:
def filter(df, val_cols, order, cutoff_freq, framerate=None):

    """
    Applies low-pass Buterworth filter on offline FicTrac data. 
    Does not drop NA values.

    Parameters:
    -----------
    df (DataFrame): Dataframe of FicTrac data generated from parse_dats()

    val_cols (list): List of column names from `df` to be filtered. 

    order (int): Order of the filter.

    cutoff_freq (float): The cutoff frequency for the filter in Hz.

    framerate (float): The mean framerate used for acquisition with FicTrac. 
        If None, will use the average frame rate as computed in the input 'df'. 
        Can be overridden with a provided manual value. Default is None.

    Returns:
    --------
    A dataframe with both the filtered and raw values. 
    Filtered columns are denoted with a "filtered_" prefix.
    """
        
    if framerate == None:
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

    return df_with_filtered


def plot_filtered(df, val_cols, time_col, 
                  order, cutoff_freq,
                  val_labels=None, time_label=None,
                  view_perc=100, 
                  theme=None,
                  save_path_to=None, show_plots=True):

    """
    Apply a low-pass Butterworth filter on offline FicTrac data. 
    Plot filtered vs. non-filtered data. 
    Purpose is to assess filter parameters on data. 

    Parameters:
    -----------
    df (DataFrame): Filtered dataframe of FicTrac data generated from parse_dats(). 
        Should have columns with the "filtered_" prefix. 

    val_cols (list): List of column names from `df` to be Fourier-transformed. 

    time_col (str): Column name from `df` that specifies time. 

    order (int): Order of the filter.

    cutoff_freq (float): The cutoff frequency for the filter in Hz.

    val_labels (list): List of labels for the plot's y-axis. If None, will 
        be a formatted version of cmap_cols. Default is None.

    time_label (str): Label for the plot's time-axis. 

    view_perc (float): Specifies how much of the data to plot as an initial 
        percentage. Useful for assessing the effectieness of the filter over longer 
        timecourses. Default is set to 1, i.e. plot the data over the entire 
        timecourse. Must be a value between 0 and 1.

    theme (str or None): A pre-defined colour theme for plotting. If None,
        does not apply a theme. Default is None.

    save_path_to (str): Absolute path to which to save the plots as .png and .svg files. 
        If None, will not save the plots. Default is None. 

    show_plots (bool): If True, will show plots, but will not output Bokeh plotting 
        objects. If False, will not show plots, but will output Bokeh plotting objects. 
        If both save and show_plots are True, .html plots will be generated, in addition 
        to the .png plots. Default is True.

    Returns:
    ---------
    if show_plots is True: will show plots instead of outputting bokeh.plotting.figure object.
    if show_plots is False: will output bokeh.plotting.figure objects, instead of showing plots.
    if save_path_to is not None: will save .png plots to specified path. 
    if save_path_to is None: will not save plots.
    """
    
    assert (0 <= view_perc <= 100), \
        f"The view percentage, {view_perc}, must be between 0 and 100."
    assert (len(df.filter(regex="^filtered_").columns) > 0), \
        "At least one column in the dataframe must begin with 'filtered_'"
    
    # Format axes labels:
    if time_label == None:
        time_label = time_col.replace("_", " ")
    if val_labels == None:
        val_labels = [val_col.replace("_", " ") for val_col in val_cols]
    
    # View the first _% of the data:
    domain = int(view_perc/100 * len(df[time_col])) 

    plots = []
    for i, val_col in enumerate(val_cols):
        assert (len(df[time_col] == len(df[val_col]))), \
            "time and vals are different lengths! They must be the same."
        assert (time_col in df), \
            f"The column, {time_col}, is not in the input dataframe."
        assert (val_col in df), \
            f"The column, {val_col}, is not in the input dataframe."
        assert ("ID" in df), \
            f"The column 'ID' is not in in the input dataframe."
        assert ("filtered_" in val_col), \
            f"The column, {val_col}, does not begin with the 'filtered_' prefix." 
        
        # Plot:
        p = figure(
            width=1600,
            height=500,
            x_axis_label=time_label,
            y_axis_label=val_labels[i] 
        )
        p.line(
            x=df[time_col][:domain],
            y=df[val_col.replace("filtered_","")][:domain],
            color=bokeh.palettes.brewer["Paired"][3][0],
            legend_label="raw"
        )
        p.line(
            x=df[time_col][:domain],
            y=df[val_col][:domain],
            color=bokeh.palettes.brewer["Paired"][3][1],
            legend_label="filtered"
        )
        p.title.text = f"first {view_perc}% with butterworth filter: cutoff = {cutoff_freq} Hz, order = {order}"
        p.title.text_font_size = "14pt"
        p.yaxis.axis_label_text_font_size = "12pt"
        p.yaxis.axis_label_text_font_size = "12pt"
        p.xaxis.axis_label_text_font_size = "12pt"
        load_plot_theme(p, theme=theme, has_legend=True) 

        # Output:
        if save_path_to is not None:
            filename = join(save_path_to, val_col)
            p.output_backend = "svg"
            export_svgs(p, filename=filename + ".svg")
            export_png(p, filename=filename + ".png")
            output_file(filename=filename + ".html", 
                        title=filename)
            
        if show_plots == True:
            # In case this script is run in Jupyter, change output_backend 
            # back to "canvas" for faster performance:
            p.output_backend = "canvas"
            show(p)

        # In case show_plots is False:
        plots.append(p)

    if show_plots == False:
        return plots


def plot_trajectory(df, cmap_cols, low=0, high_percentile=95, respective=False, 
                    cmap_labels=None,
                    order=2, cutoff_freq=4, 
                    palette = cc.CET_L16, size=2.5, alpha=0.3, 
                    theme=None,
                    show_start=False, 
                    save_path_to=None, show_plots=True):
    
    """
    Plot XY FicTrac coordinates of the individual with a linear colourmap for 
    a each element in `cmap_cols`. 
    
    Parameters:
    -----------
    df (DataFrame): Dataframe of FicTrac data generated from parse_dats()

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

    respective (bool): If True, will re-scale colourmap for each individual to 
        their respective 'high_percentile' cut-off value. If False, will use
        the 'high_percentile' value computed from the population, i.e. from `df`. 
        Default is False. 

    cmap_cols (list): List of column names from `df` to be colour-mapped. 

    cmap_labels (list): List of labels for the plots' colourbars. If None, will 
        be a formatted version of cmap_cols. Default is None.

    order (int): Order of the filter.

    cutoff_freq (float): The cutoff frequency for the filter in Hz.

    palette (list): A list of hexadecimal colours to be used for the colour map.

    size (float): The size of each datapoint specifying XY location. 

    alpha(float): The transparency of each datapoint specifying XY location.
        Must be between 0 and 1.

    theme (str or None): A pre-defined colour theme for plotting. If None,
        does not apply a theme. Default is None.

    show_start (bool): If True, will plot a marking to explicitly denote the start 
        site. Default is False. 
    
    save_path_to (str): Absolute path to which to save the plots as .png and .svg files. 
        If None, will not save the plots. Default is None. 

    show_plots (bool): If True, will show plots, but will not output Bokeh plotting 
        objects. If False, will not show plots, but will output Bokeh plotting objects. 
        If both save and show_plots are True, .html plots will be generated, in addition 
        to the .png plots. Default is True.

    Returns:
    ---------
    if show_plots is True: will show plots instead of outputting bokeh.plotting.figure object.
    if show_plots is False: will output bokeh.plotting.figure objects, instead of showing plots.
    if save_path_to is not None: will save .png plots to specified path. 
    if save_path_to is None: will not save plots.
    """

    assert (low >= 0), "The low end of the colour map range must be non-negative"
    assert ("X_mm" in df), "The column, 'X_mm', is not in the input dataframe."
    assert ("Y_mm" in df), "The column, 'Y_mm', is not in the input dataframe."
    assert ("ID" in df), "The column 'ID' is not in in the input dataframe."
  
    # Format axes labels:
    if cmap_labels == None:
        cmap_labels = [cmap_col.replace("_", " ") for cmap_col in cmap_cols]

    plots = []
    for i, cmap_col in enumerate(cmap_cols):
        
        assert (cmap_col in df), \
            f"The column, {cmap_col}, is not in the input dataframe."
        assert (len(df["X_mm"] == len(df["Y_mm"]))), \
            "X_mm and Y_mm are different lengths! They must be the same."

        if respective == False:
            # Normalize colourmap range to population:
            high = np.percentile(df[cmap_col], high_percentile)
        elif respective == True:
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
        
        if show_start == True:
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
        load_plot_theme(p, theme=theme)

        # Output:
        if save_path_to is not None:
            filename = save_path_to + f"fictrac_XY_{cmap_col}"
            p.output_backend = "svg"
            export_svgs(p, filename=filename + ".svg")
            export_png(p, filename=filename + ".png")
            output_file(filename=filename + ".html", 
                        title=filename)
            
        if show_plots == True:
            # In case this script is run in Jupyter, change output_backend 
            # back to "canvas" for faster performance:
            p.output_backend = "canvas"
            show(p)

        # In case show_plots is False:
        plots.append(p)

    if show_plots == False:
        return plots


# Banned substrings to be used in `plot_histograms` and `plot_ecdfs`:
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
                     "ID",
                     "__"] 


# TODO: Move to a more general file:
def ban_columns_with_substrings(df, substrings=banned_substrings):

    """
    From a dataframe, return only columns whose names do not contain specified substrings.

    Parameters:
    -----------
    df: A dataframe. 
    substrings: A list of substrings to ban from `df`'s column names.

    Returns:
    --------
    A list of all of `df`'s column names that do not contain the substrings listed in `substrings`.
    """
    
    all_cols = list(df.columns)
    
    banned_cols = []
    for col in all_cols:
        for substring in banned_substrings:
            if substring in col:
                banned_cols.append(col)
                break

    ok_cols = [col for col in all_cols if col not in banned_cols]

    return ok_cols


def plot_histograms(df, cols=None, labels=None, 
                    cutoff_percentile=95,
                    theme=None,
                    save_path_to=None, show_plots=True): 

    """
    Generate histograms for multiple FicTrac variables. 

    Parameters:
    -----------
    df (DataFrame): Dataframe of FicTrac data generated from parse_dats()

    cols (list): List of strings specifying column names in `df`. If None, 
        uses default columns that specify real-world and 'lab' kinematic measurements. 
        See `banned_substrings`. 
        Otherwise, will use both input arguments AND the default columns. Default is None.

    labels (list): List of strings specifying the labels for the histograms' x-axes.
        Its order must correspond to 'cols'. 

    cutoff_percentile (float): Specifies the percentile of the AGGREGATE population data. 
        Plots a line at this value. Default is 95th percentile. 

    theme (str or None): A pre-defined colour theme for plotting. If None,
        does not apply a theme. Default is None.
        
    save_path_to (str): Absolute path to which to save the plots as .png and .svg files. 
        If None, will not save the plots. Default is None. 

    show_plots (bool): If True, will show plots, but will not output Bokeh plotting 
        objects. If False, will not show plots, but will output Bokeh plotting objects. 
        If both save and show_plots are True, .html plots will be generated, in addition 
        to the .png plots. Default is True.

    Returns:
    ---------
    if show_plots is True: will show plots instead of outputting bokeh.plotting.figure object.
    if show_plots is False: will output bokeh.plotting.figure objects, instead of showing plots.
    if save_path_to is not None: will save .png plots to specified path. 
    if save_path_to is None: will not save plots.
    """

    assert ("ID" in df), "The column 'ID' is not in in the input dataframe."
    
    ok_cols = ban_columns_with_substrings(df)

    if cols == None:
        cols = ok_cols
    else:
        cols = ok_cols + cols 
        for col in cols:
            assert (col in df), f"The column, {col}, is not in the input dataframe."
    
    if labels == None:
        labels = [col.replace("_", " ") for col in cols] 

    plots = []
    for i, col in enumerate(cols):
        p = iqplot.histogram(data=df,
                             cats=['ID'],
                             val=col,
                             density=True,
                             width=1000,
                             height=500)
        
        cutoff_line = Span(location=np.percentile(df[col], cutoff_percentile), 
                           dimension="height", 
                           # line_color="#e41a1c",
                           line_color = "#775a42",
                           line_dash="dashed",
                           line_width=2)
        
        p.legend.location = "top_right"
        p.legend.title = "ID"
        load_plot_theme(p, theme=theme, has_legend=True)
        p.title.text = f" with aggregate {cutoff_percentile}% mark"
        p.xaxis.axis_label = labels[i]
        p.xaxis.axis_label_text_font_size = "12pt"
        p.yaxis.axis_label_text_font_size = "12pt"
        p.add_layout(cutoff_line)
            
        # Output:
        if save_path_to is not None:
            filename = join(save_path_to, f"fictrac_histogram_by_ID_{col}")
            p.output_backend = "svg"
            export_svgs(p, filename=filename + ".svg")
            export_png(p, filename=filename + ".png")
            output_file(filename=filename + ".html", 
                        title=filename)
        
        if show_plots == True:
            # In case this script is run in Jupyter, change output_backend 
            # back to "canvas" for faster performance:
            p.output_backend = "canvas"
            show(p)

        # In case show_plots is False:
        plots.append(p)

    if show_plots == False:
        return plots


def plot_ecdfs(df, cols=None, labels=None, 
               cutoff_percentile=95, 
               theme=None,
               save_path_to=None, show_plots=True):

    """
    Generate ECDFs for multiple FicTrac variables. 

    Parameters:
    -----------
    df (DataFrame): Concatenated dataframe of FicTrac data generated from parse_dats()

    cols (list): List of strings specifying column names in 'df'. If None, 
        uses default columns that specify real-world and 'lab' kinematic measurements.
        See `banned_substrings`
        Otherwise, will use both input arguments AND the default columns. Default is None.

    labels (list): List of strings specifying the labels for the ECDFs' x-axes.
        Its order must correspond to 'cols'. 

    cutoff_percentile (float): Specifies the percentile of the AGGREGATE population data. 
        Plots a line at this value. Default is 95th percentile. 

    theme (str or None): A pre-defined colour theme for plotting. If None,
        does not apply a theme. Default is None.
    
    save_path_to (str): Absolute path to which to save the plots as .png and .svg files. 
        If None, will not save the plots. Default is None. 

    show_plots (bool): If True, will show plots, but will not output Bokeh plotting 
        objects. If False, will not show plots, but will output Bokeh plotting objects. 
        If both save and show_plots are True, .html plots will be generated, in addition 
        to the .png plots. Default is True.

    Returns:
    ---------
    if show_plots is True: will show plots instead of outputting bokeh.plotting.figure object.
    if show_plots is False: will output bokeh.plotting.figure objects, instead of showing plots.
    if save_path_to is not None: will save .png plots to specified path. 
    if save_path_to is None: will not save plots.
    """

    assert ("ID" in df), "The column 'ID' is not in in the input dataframe."
    
    ok_cols = ban_columns_with_substrings(df)

    if cols == None:
        cols = ok_cols
    else:
        cols = ok_cols + cols 
        for col in cols:
            assert (col in df), f"The column, {col}, is not in the input dataframe."
    
    if labels == None:
        labels = [col.replace("_", " ") for col in cols] 

    plots = []
    for i, col in enumerate(cols):
        p = iqplot.ecdf(data=df,
                        cats=["ID"],
                        val=col,
                        kind="colored",
                        width=1000,
                        height=500)
        
        cutoff_line = Span(location=np.percentile(df[col], cutoff_percentile), 
                           dimension="height", 
                           line_color="#775a42",
                           line_dash="dashed",
                           line_width=2)
        
        p.legend.location = 'top_right'
        p.legend.title = "ID"
        load_plot_theme(p, theme=theme, has_legend=True)
        p.title.text = f" with aggregate {cutoff_percentile}% mark"
        p.xaxis.axis_label = labels[i]
        p.xaxis.axis_label_text_font_size = "12pt"
        p.yaxis.axis_label_text_font_size = "12pt"
        p.add_layout(cutoff_line)
        
        # Output:
        if save_path_to is not None:
            filename = save_path_to + f"fictrac_ecdfs_{col}"
            
            p.output_backend = "svg"
            export_svgs(p, filename=filename + ".svg")
            export_png(p, filename=filename + ".png")
            output_file(filename=filename + ".html", 
                        title=filename)
            
        if show_plots == True:
            # In case this script is run in Jupyter, change output_backend 
            # back to "canvas" for faster performance:
            p.output_backend = "canvas"
            show(p)

        # In case show_plots is False:
        plots.append(p)

    if show_plots == False:
        return plots


def add_stimulus_annotation (p, style,
                             start, end, top, bottom, 
                             alpha, level="underlay"):

    """
    
    Add a stimulus annotation to a Bokeh plotting object. 

    Parameters:
    -----------
    p: A Bokeh plotting object
    style (str): One of three stimulus annotation styles: 1) "horiz_bar", which
        is a horizontal bar that denotes the duration of the stimulus, 
        2) "background_box", which is an underlaid box that denotes the
        duration of the stimulus, or 3) "double_bars" which is a pair of
        vertical bars that denote the start and end of the stimulus. 
    start (fl): Beginning of stimulus presentation in data coordinates.
    end (fl): End of stimulus presentation in data coordinates.
    top (fl): Applies only if `style`="horiz_bar". The top of the horizontal bar
        in data coordinates.
    bottom (fl): Applies only if `style`="horiz_bar". The bottom of the horizontal
        bar in data coordinates. 
    alpha (fl): The transparency of the stimulus annotation. Must be between 
        0 and 1. 
    level (str): The display level of the stimulus annotation, relative to the plot. 
        Default is "underlay". If `style`="background_box", can only be "underlay".
    
    Returns:
    --------
    `p` with stimulus annotation. 

    """

    # TODO: Add None option to pass default colours, which an be overriden by arg
    # TODO: "background_box" requires top and bottom as args, even though it doesn't use them; incorporate None

    assert (style == "horiz_bar" or "background_box" or "double_bars"), \
        f"{style} is not a valid entry for `style`. Please input either \
        'horiz_bar', 'background_box', or 'double_bars'."

    if style == "horiz_bar":
        bar = BoxAnnotation(left=start, 
                            right=end, 
                            top=top,
                            bottom=bottom,
                            fill_alpha=alpha, 
                            fill_color="#787878", 
                            level=level)
        p.add_layout(bar)

    elif style == "background_box":
        box = BoxAnnotation(left=start, 
                            right=end, 
                            fill_alpha=alpha, 
                            fill_color="#B6A290", 
                            level="underlay")
        p.add_layout(box)

    elif style == "double_bars":
        line_colour = "#775a42"
        start_line = Span(location=start, 
                          dimension="height", 
                          line_color=line_colour,
                          line_dash="dotted",
                          line_width=2) 
        end_line = Span(location=end, 
                        dimension="height",
                        line_color=line_colour,
                        line_dash="dotted",
                        line_width=2)
        p.add_layout(start_line)
        p.add_layout(end_line) 

    else:
        print()

    return p


# TODO: Move to a more general file:
def aggregate_trace(df, group_by, method="mean", round_to=0, f_steps=1):
    
    """
    From a dataframe with time series data, round the data, do a groupby,
    compute either the mean or the median, then reset the index. 

    Parameters:
    ------------
    df: A Pandas dataframe.
    group_by: A list of columns in `df` with which to perform the groupby. 
    method: The method by which to aggregate the data. Must be either 
        "mean" or "median". Is "mean" by default. 
    round_to: The place value with which to round the data. 
    f_steps (fl): The fraction of steps from which to downsample `df`. 

    Return:
    -------
    A dataframe of aggregate statistics. 
    """

    assert (method=="mean" or method=="median"), \
        "The aggregation `method` must be 'mean' or 'median'."
    assert (1 >= f_steps > 0), \
        f"`f_steps`, {f_steps}, must be greater than 0 and less than or equal to 1."
    
    # Round:
    rounded = df.round(round_to)

    # Downsample:
    indices = np.round(np.linspace(0, len(rounded.index), int(len(rounded.index)*f_steps + 1)))
    indices = [int(index) for index in indices]
    indices.pop()
    downsampled = rounded.iloc[indices,:]
    grouped = downsampled.groupby(group_by) 

    # Aggregate:
    if method=="mean":
        mean_df = grouped.mean().reset_index()
        return mean_df

    elif method=="median":
        median_df = grouped.median().reset_index()
        return median_df


def plot_aggregate_trace(df, group_by, val_col, time_col, 
                         val_label, time_label, 
                         palette, 
                         aggregation_method="mean", 
                         y_range=None,
                         legend_labels=None, theme=None,
                         mean_alpha=0.7, id_alpha=0.008, 
                         line_width=5, 
                         round_to=0, f_steps=1
                         ):

    """
    
    # TODO: ADD DOCS
    * N.B. Will ALWAYS make a legend. 

    """

    assert ("ID" in df), "The column 'ID' is not in in the input dataframe."
    assert ("trial" in df), "The column 'trial' is not in in the input dataframe."

    # TODO: Add None option for args for val_label and time_label
    # TODO: Add show option and save option

    p = figure(width=1000,
               height=400,
               y_range=y_range,
               x_axis_label=time_label,
               y_axis_label=val_label)
    
    grouped = df.groupby(group_by)

    for i, ((name,group), hue) in enumerate(zip(grouped, palette)):

        # Make dataframes:
        agg_df = aggregate_trace(group, 
                                 ["trial", time_col], 
                                 method=aggregation_method, 
                                 round_to=round_to, f_steps=f_steps
                                 ) 
        grouped_by_id = group.groupby(["ID"]) 

        assert len(palette)==len(grouped), \
            f"The lengths of `palette`, and `df.groupby({grouped})` must be equal."
        
        if legend_labels==None:
            legend_label = f"{name} | n={len(grouped_by_id)}"
        else:
            assert len(grouped)==len(legend_labels), \
                f"The lengths of `legend_labels`, `palette`, `df.groupby({grouped})` \
                must be equal."
            legend_label =  legend_labels[i]

        # Mean trace:
        p.line(x=agg_df[time_col], y=agg_df[val_col], 
               legend_label=legend_label, 
               color=hue,
               line_width=line_width,
               alpha=mean_alpha)

        # ID traces:
        for _, id_group in grouped_by_id:
            
            p.line(x=id_group[time_col], y=id_group[val_col], 
                   color=hue,
                   line_width=1, 
                   alpha=id_alpha, 
                   legend_label=legend_label,  
                   level="underlay")

    if theme==None:
        pass
    else:
        load_plot_theme(p, theme=theme, has_legend=True)
    
    return p 
    


def main():
    
    # TODO: Move this documentation to a README.md in software/
    # parser = argparse.ArgumentParser(description = __doc__)
    # parser.add_argument("acq_mode", 
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

    # TODO: Write docs for script arguments, maybe in a README.md
    # TODO: Don't hardcode .yaml file name, pass it in as an argument instead.
    # TODO: Specify default .yaml values, for key-value pairs that are unspecified:
    with open("fictrac_analyses_params.yaml") as f:

        params = yaml.load(f, Loader=yaml.FullLoader)
        # print(params)

    root = params["root"]
    acq_mode = params["acq_mode"]
    acq_mode = params["acq_mode"]
    acq_mode = "offline"
    ball_radius = params["ball_radius"]

    val_cols = params["val_cols"]
    filtered_val_cols = ["filtered_" + val_col for val_col in val_cols]
    val_labels = params["val_labels"]

    time_col = params["time_col"]
    time_label = params["time_label"]

    cutoff_freq = params["cutoff_freq"]
    order = params["order"]
    framerate = params["framerate"]

    view_perc = params["view_perc"]

    cmap_labels = params["cmap_labels"]
    alpha_cmap = params["alpha_cmap"]
    percentile_max_clamp = params["percentile_max_clamp"]
    respective = params["respective"]
    respective = False

    no_save = params["no_save"]
    show_plots = params["show_plots"]

    # Parse FicTrac inputs:
    dfs = parse_dats(root, ball_radius, acq_mode, do_confirm=False)

    # Save each individual bokeh plot to its respective ID folder. 
    folders = sorted([path.absolute() for path in Path(root).rglob("*/fictrac")])

    save_paths = []
    for df, folder in zip(dfs, folders):
        # Generate individual ID plots:
        print(f"Generating individual plots for {folder} ...")
        save_path_to = join(folder, "plots/")
        save_paths.append(save_path_to)

        if exists(save_path_to):
            rmtree(save_path_to)
        mkdir(save_path_to)

        if no_save == True:
            save_path_to = None

        # Plot FFT power spectrum:
        plot_fft(df, 
                 val_cols=val_cols, 
                 time_col=time_col, 
                 val_labels=val_labels,
                 time_label=time_label,
                 cutoff_freq=cutoff_freq, 
                 save_path_to=save_path_to,
                 show_plots=show_plots) 

        # Plot raw vs. filtered:
        plot_filtered(df, 
                              val_cols=filtered_val_cols, 
                              time_col=time_col, 
                              val_labels=val_labels, 
                              time_label=time_label,
                              cutoff_freq=cutoff_freq, 
                              order=order, 
                              view_perc=view_perc,
                              save_path_to=save_path_to,
                              show_plots=show_plots)

        # Plot XY
        cm = get_all_cmocean_colours()
        plot_trajectory(df,
                        cmap_cols=filtered_val_cols,
                        high_percentile=percentile_max_clamp,
                        respective=respective,
                        cmap_labels=cmap_labels,
                        palette=cm["thermal"],
                        alpha=alpha_cmap,
                        save_path_to=save_path_to,
                        show_plots=show_plots)

    # Generate population plots:
    print("Generating population plots ...")

    # Concatenate data into a population:
    concat_df = pd.concat(dfs).dropna()
    
    save_path_popns = join(root, "popn_plots/")
    if exists(save_path_popns):
        rmtree(save_path_popns)
    mkdir(save_path_popns)
    subdirs = ["histograms/", "ecdfs/"]
    [mkdir(join(root, "popn_plots/", subdir)) for subdir in subdirs]

    save_path_hists = join(root, "popn_plots/", "histograms/")
    save_path_ecdfs = join(root, "popn_plots/", "ecdfs/")

    # Plot histograms:
    print("Generating histograms ...")
    plot_histograms(concat_df, 
                    cutoff_percentile=percentile_max_clamp,
                    save_path_to=save_path_hists, 
                    show_plots=False)

    # Plot ECDFs:
    print("Generating ECDFs ...")
    plot_ecdfs(concat_df,
               cutoff_percentile=percentile_max_clamp,
               save_path_to=save_path_ecdfs, 
               show_plots=False)
    

if __name__ == "__main__":
    main()