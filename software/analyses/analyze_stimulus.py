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
                                         on=common_col, fill_method=fill_method)
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
                                         on=common_col, fill_method=None)
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
    for _, df_merged in dfs_merged:
        df_merged["stim_X_mm"] = df_merged["stim_X_mm"] + \
                                 (df_merged["dist_from_stim_mm"] * \
                                 np.cos(-1 * np.deg2rad(df_merged["Stepper output (degs)"] - np.pi/2))) 
        df_merged["stim_Y_mm"] = df_merged["stim_Y_mm"] + \
                                 (df_merged["dist_from_stim_mm"] * \
                                 np.sin(-1 * np.deg2rad(df_merged["Stepper output (degs)"] - np.pi/2))) 
        
        dfs_merged.append(df_merged)

    dfs_merged = pd.concat(dfs_merged)
    return dfs_merged