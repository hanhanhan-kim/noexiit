#!/usr/bin/env python3

"""
Process programmatic stimuli used for NOEXIIT. 
When run as a script, transforms .csv stimulus file into a single concatenated
Pandas dataframe with some additional columns. Includes functions for merging
stimulus .csvs with other dataframes, such as those from FicTrac and/or 
DeepLabCut. 
"""

import glob 
from os.path import isdir, join, split

import pandas as pd
from pandas.api.types import is_numeric_dtype
import numpy as np
import scipy.interpolate as spi

from bokeh.io import output_file, export_png, export_svgs, show
from bokeh.transform import linear_cmap
from bokeh.plotting import figure
from bokeh.models import ColorBar, ColumnDataSource, Span
from bokeh.layouts import gridplot
import bokeh.palettes 
import colorcet as cc

from analyze_fictrac import unconcat_df


def get_smaller_last_val(df_1, df_2, common_col):
    """
    Compare the last value for a column shared between two dataframes. 
    Return the smaller value of these values as a float.  
    """
    assert common_col in df_1 and common_col in df_2, \
        f"{df_1} and {df_2} do not share {common_col}"
    assert is_numeric_dtype(df_1[common_col]), \
        f"The values of {common_col} in {df_1} is not numeric, e.g. float64, etc."
    assert is_numeric_dtype(df_2[common_col]), \
        f"The values of {common_col} in {df_1} is not numeric, e.g. float64, etc."

    compare = float(df_1[common_col].tail(1)) > float(df_2[common_col].tail(1))
    if compare is True:
        return float(df_2[common_col].tail(1))
    else:
        return float(df_1[common_col].tail(1))


def parse_2dof_stimulus (root, nesting, servo_min, servo_max, servo_touch):
    """
    Formats 2dof motor stimulus .csv file. Maps 0 to 180 linear servo angle range
    to real distances in mm. 

    Parameters:
    -----------
    root (str): Absolute path to the root directory. I.e. the outermost 
        folder that houses the stimulus .csv files
    nesting (int): Specifies the number of folders that are nested from the
        root directory. I.e. the number of folders between root and the
        'stimulus' subdirectory that houses the input .csv files. 
    servo_min (fl): The minimum linear servo extension. Must be in mm.
    servo_max (fl): The maximum linear servo extension. Must be in mm. 
    servo_touch (fl): The linear servo extension length (mm) at which the stimulus 
        touches the insect on the ball. Will often be the same as 'servo_max'. 

    Returns:
    --------
    """
    csvs = sorted(glob.glob(join(root, nesting * "*/", "stimulus/*.csv")))
    
    for csv in csvs:
        head = split(csv)[0]
        assert isdir(head), \
            f"The directory, {head}, does not exist."
    
    # Generate function to map servo parameters:
    f_servo = spi.interp1d(np.linspace(0,180), np.linspace(servo_min,servo_max))

    dfs = []
    for i, csv in enumerate(csvs):
        df = pd.read_csv(csv)

        assert "Servo output (degs)" in df, \
            f"The column 'Servo output (degs)' is not in the dataframe, {df}."

        # Map:
        df["Servo output (mm)"] = f_servo(df["Servo output (degs)"])
        # Convert to distance from stim: 
        df["dist_from_stim_mm"] = servo_touch - df["Servo output (mm)"]
        
        # Assign animal number:
        df['animal'] = str(i)

        # My older stimulus csvs have this col instead of "secs_elapsed":
        if "Elapsed time" in df:
            df = df.rename(columns={"Elapsed time": "secs_elapsed"})

        dfs.append(df)
    
    dfs = pd.concat(dfs)
    return dfs


def merge_stimulus_with_data (stim_dfs, dfs_1, dfs_2=None, 
                              common_col="secs_elapsed", fill_method="ffill"):
    """
    Merge, according to a common column, the ordered stimulus dataframe with 
    one or two other ordered dataframes--namely, the FicTrac data and/or 
    DeepLabCut data. Dataframes will usually be timeseries, so will be ordered by 
    time. Fills NaN values with either a forward fill or linear interpolation, 
    then truncates the merged dataframe by the earliest last valid observation 
    seen across the input dataframes. 

    Parameters:
    -----------
    stim_dfs: A time-series dataframe of the stimulus presentation. 
    dfs_1: A time-series dataframe to be merged with 'stim_dfs'.
    dfs_2: An additional time-series dataframe to be also merged with 'stim_dfs'.
    common_col (str): A common column against which to merge the dataframes. 
        Will be some ordered unit such as time. 
    fill_method (str): Specifies how to treat NaN values upon merge. 
        Either 'ffill' for forward fill, or 'linear' for linear interpolation. 
        Forward fill fills the NaNs with the last valid observation, until the
        next valid observation. Linear interpolation fits a line based on two 
        flanking valid observations. The latter works only on columns with numeric 
        values; non-numerics are forward-filled. 

    Returns:
    --------
    A single merged dataframe consisting of the stimulus dataframe and the other
        input dataframes. 
    """
    
    # TODO: assert "animal" in all dataframes and refactor dfs_2 is not None

    assert common_col in stim_dfs and common_col in dfs_1, \
        f"{stim_dfs} and {dfs_1} do not share {common_col}"
    if dfs_2 is not None:
        assert common_col in stim_dfs and common_col in dfs_2, \
            f"{stim_dfs} and {dfs_2} do not share {common_col}"

    stim_dfs = unconcat_df(stim_dfs)
    dfs_1 = unconcat_df(dfs_1)
    
    assert len(stim_dfs) == len(dfs_1), \
        f"{stim_dfs} and {dfs_1} possess a different number of experiments."
    if dfs_2 is not None:
        dfs_2 = unconcat_df(dfs_2)
        assert len(stim_dfs) == len(dfs_2), \
            f"{stim_dfs} and {dfs_2} possess a different number of experiments."
    
    dfs_merged = []
    for i, stim_df in enumerate(stim_dfs): 
        
        smaller_last_val = get_smaller_last_val(stim_df, dfs_1[i], common_col)

        if fill_method is "ffill":
            df_merged = pd.merge_ordered(stim_df, dfs_1[i], 
                                         on=[common_col, "animal"], fill_method=fill_method)
            df_merged = df_merged[df_merged[common_col] < smaller_last_val]    
            
            if dfs_2 is not None: 
                if smaller_last_val > get_smaller_last_val(stim_df, dfs_2[i], 
                                                           common_col):
                    smaller_last_val = get_smaller_last_val(stim_df, dfs_2[i], 
                                                            common_col)
                df_merged = pd.merge_ordered(df_merged, dfs_2[i], on=common_col,
                                                fill_method=fill_method)
        
        elif fill_method is "linear":
            df_merged = pd.merge_ordered(stim_df, dfs_1[i], 
                                         on=[common_col, "animal"], 
                                         fill_method=None)
            df_merged = df_merged[df_merged[common_col] < smaller_last_val] 
            df_merged = df_merged.interpolate(method=fill_method)

            if dfs_2 is not None:
                if smaller_last_val > get_smaller_last_val(stim_df, dfs_2[i], common_col):
                    smaller_last_val = get_smaller_last_val(stim_df, dfs_2[i],
                                                            common_col) 
                df_merged = pd.merge_ordered(df_merged, dfs_2[i], on=common_col, fill_method=None)
                df_merged = df_merged[df_merged[common_col] < smaller_last_val] 
                df_merged = df_merged.interpolate(method=fill_method)
                
        dfs_merged.append(df_merged)

    dfs_merged = pd.concat(dfs_merged)

    if fill_method is "linear":
        # Ffill any remaining non-numeric values:
        dfs_merged = dfs_merged.ffill(axis=0)

    return dfs_merged


def make_stimulus_trajectory(dfs_merged):
    """
    Generate stimulus trajectories from the 2DOF stimulus relative to the same 
    frame of reference as the tethered insect's trajectory, as computed by 
    FicTrac. Assumes that the reference direction for the stimulus angle results 
    in the stimulus facing parallel and co-linear to the beetle in real untethered 
    space.  

    Parameters:
    -----------
    dfs_merged: A single dataframe consisting of pre-processed stimulus data 
        merged with at least a FicTrac dataframe. 
    
    Return:
    -------
    A single dataframe with columns for the X and Y Cartesian coordinates of the stimulus. 

    """
    assert "X_mm" in dfs_merged and "Y_mm" in dfs_merged \
        and "dist_from_stim_mm" in dfs_merged, \
        f"The 'X_mm', 'Y_mm', and 'dist_from_stim_mm' columns are not in {dfs_merged}"

    dfs_merged = unconcat_df(dfs_merged)

    dfs_trigged = []
    for _, df_merged in enumerate(dfs_merged):

        df_merged['stim_X_mm'] = df_merged.apply(lambda row: (row["X_mm"] + \
            (row["dist_from_stim_mm"] * np.cos(np.deg2rad(row["Stepper output (degs)"])))), 
            axis=1)
        df_merged['stim_Y_mm'] = df_merged.apply(lambda row: (row["Y_mm"] + \
            (row["dist_from_stim_mm"] * np.sin(np.deg2rad(row["Stepper output (degs)"])))), 
            axis=1)
        
        dfs_trigged.append(df_merged)

    dfs_trigged = pd.concat(dfs_trigged)
    return dfs_trigged


def plot_fictrac_XY_with_stim(dfs, low=0, high_percentile=95, respective=False, 
                              cmap_col="secs_elapsed", cmap_label="time (s)", 
                              palette_beetle=bokeh.palettes.Blues256[150:70:-1], 
                              palette_stim=bokeh.palettes.Greys256[150:70:-1], 
                              size=2.0, alpha=0.3, 
                              show_start=False, 
                              save_path=None, show_plots=True):
    """
    Plot XY FicTrac coordinates of both the tethered animal and the 2-DOF stimulus. 
    Adds a linear colourmap for a FicTrac variable of choice. 
    
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
    cmap_label (str): Label for both colour maps. 
    palette_beetle (list): A list of hexadecimal colours to be used for the beetle's 
        colour map.
    palette_stim (list): A list of hexadecimal coloours to be used for the stimulus' 
        colour map.
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
        
        assert len(df["X_mm"] == len(df["Y_mm"])), \
            "X_mm and Y_mm are different lengths! They must be the same."
        
        source = ColumnDataSource(df)
        
        if respective is True:
            high = np.percentile(df[cmap_col], high_percentile)
            # also change colorbar labels so max has =< symbol
        
        mapper_beetle = linear_cmap(field_name=cmap_col, 
                             palette=palette_beetle, 
                             low=low, 
                             high=high)
        
        mapper_stim = linear_cmap(field_name=cmap_col, 
                             palette=palette_stim, 
                             low=low, 
                             high=high)
        
        p = figure(background_fill_color="#f8f5f2", 
                   width=800,
                   height=800,
                   x_axis_label="X (mm)",
                   y_axis_label="Y (mm)")
        
        # beetle:
        p.circle(source=source,
                 x="X_mm",
                 y="Y_mm",
                 color=mapper_beetle,
                 size=size,
                 alpha=alpha)
        
        # stimulus:
        p.circle(source=source,
                 x="stim_X_mm", 
                 y="stim_Y_mm", 
                 color=mapper_stim, 
                 size=size, 
                 alpha=alpha)

        color_bar_beetle = ColorBar(color_mapper=mapper_beetle['transform'], 
                                    title="beetle " + cmap_label,
                                    title_text_font_size="7pt",
                                    background_fill_color="#f8f5f2",
                                    width=10,
                                    location=(0,0))
        
        color_bar_stim = ColorBar(color_mapper=mapper_stim['transform'], 
                                  title="stimulus " + cmap_label,
                                  title_text_font_size="7pt",
                                  background_fill_color="#f8f5f2",
                                  width=10,
                                  location=(0,0))
        
        if show_start is True:
            # Other options include .cross, .circle_x, and .hex:
            p.circle(x=df["X_mm"][0], 
                     y=df["Y_mm"][0], 
                     size=12,
                     color="darkgray",
                     fill_alpha=0.5)

        p.add_layout(color_bar_beetle, "right")
        p.add_layout(color_bar_stim, "right")

        p.title.text_font_size = "14pt"
        p.xaxis.axis_label_text_font_size = '10pt'
        p.yaxis.axis_label_text_font_size = '10pt'

        p.border_fill_color = "#f8f5f2"
        p.xgrid.grid_line_color = "#efe8e2"
        p.ygrid.grid_line_color = "#efe8e2"

        bokeh_ps.append(p)

        # Output:
        if save_path is not None:
            filename = save_path + f"fictrac_XY"
            
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