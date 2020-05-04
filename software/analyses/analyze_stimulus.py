#!/usr/bin/env python3

"""
Process programmatic stimuli used for NOEXIIT. 
When run as a script, transforms .csv stimulus file into a single concatenated
Pandas dataframe with some additional columns. Includes functions for merging
stimulus .csvs with other dataframes, such as those from FicTrac and/or 
DeepLabCut. 
"""

import glob 
from os.path import isdir, join, stripext

import pandas as pd
from pandas.api.types import is_numeric_dtype

import numpy as np
import scipy.interpolate as spi


def get_smaller_last_val_in_col(df1, df2, common_col):
    """
    Compare the last value for a column shared between two dataframes. 
    Return the smaller value of these values.  
    """
    assert common_col in df1 and common_col in df2, \
        f"{df1} and {df2} do not share {common_col}"
    assert is_numeric_dtype(df1[common_col]), \
        f"The values of {common_col} in {df1} is not numeric, e.g. float64, etc."
    assert is_numeric_dtype(df2[common_col]), \
        f"The values of {common_col} in {df1} is not numeric, e.g. float64, etc."

    compare = float(df1[common_col].tail(1)) > float(df2[common_col].tail(1))
    if compare is True:
        return float(df2[common_col].tail(1))
    else:
        return float(df1[common_col].tail(1))


def parse_2dof_stimulus (root, nesting, servo_min, servo_max):
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

    Returns:
    --------
    """
    csvs = sorted(glob.glob(join(root, nesting * "*/", "stimulus/*.csv")))

    for csv in csvs:
        assert isdir(stripext(csv)), \
            f"This directory does not exist."
    
    # Generate function to map servo parameters:
    f_servo = spi.interp1d(np.linspace(0,180), np.linspace(servo_min,servo_max))

    for csv in csvs:
        df = pd.read_csv(csv)

        assert "Servo output (degs)" in df, \
            f"The column 'Servo output (degs)' is not in the dataframe."

        df["Servo output (mm)"] = f_servo(df["Servo output (degs)"])
    