#!/usr/bin/env python3

"""
Process and visualize FicTrac data with helper functions. 
"""

import numpy as np
import pandas as pd
import scipy.interpolate as spi

from bokeh.plotting import figure, output_file, show
from bokeh.layouts import gridplot

from fourier_transform import fft, bokeh_freq_domain


def parse_dats(names, framerate, ball_radius):
    '''
    Takes a list of .dat files generated by FicTrac and returns a single \
    concatenated dataframe.
    The pre-processed dataframe is given proper headings, as informed by \
    the documentation on rjdmoore's FicTrac GitHub page. 
    All values are converted into floats, except for the frame and sequence \
    counters, which are converted into ints. In addition, elapsed time is \
    converted into seconds and minutes, and the integrated X and Y positions \
    are converted to real-world values, by multiplying them against the ball \
    radius. 
    
    Parameters:

    names (list): A list of default .dat files generated by FicTrac (ver 2)
    framerate: The framerate of the acquisition of the videos FicTrac \
    analyzes. #TODO: compute the framerate, rather than take as an arg

    ball_radius (float): The radius of the ball (mm) the insect was on. \
    Used to compute the real-world values in mm.  

    Return:

    A single Pandas dataframe that concatenates all the input .dat files.
    '''
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
    
    dfs = []

    for idx, dat in enumerate(names):
        with open(dat, 'r') as f:
            next(f) # skip first row
            df = pd.DataFrame((l.strip().split(',') for l in f), columns=headers)

        # Convert all values to floats:
        df = df[headers].astype(float)

        # Convert the values in the frame and sequence counters columns to ints:
        df['frame_cntr'] = df['frame_cntr'].astype(int)
        df['seq_cntr'] = df['seq_cntr'].astype(int)

        # Compute real-world values:
        df['X_mm'] = df['integrat_x_posn'] * ball_radius
        df['Y_mm'] = df['integrat_y_posn'] * ball_radius
        df['speed_mm'] = df['animal_mvmt_spd'] * ball_radius

        # Compute elapsed time:
        df['secs_elapsed'] = df['frame_cntr']/framerate
        df['mins_elapsed'] = df['secs_elapsed']/60
        
        # Discretize minute intervals as strings:
        df['min_int'] = df['mins_elapsed'].astype('int') + 1
        df['min_int'] = df['min_int'].apply(str)

        # Assign animal number:
        df['animal'] = idx 

        dfs.append(df)

    dfs = pd.concat(dfs)
        
    return dfs


def plot_fictrac_fft(dfs, time_col, val_col, even=False, 
                     window=np.hanning, pad=1, save=True):
    # dfs.time and dfs.val? will it work?
    """
    Perform a Fourier transform on FicTrac data for each animal. Generate \
    frequency domain plots for each animal. Outputs plots. 

    Parameters:
    
    dfs (DataFrame): Concatenated dataframe of FicTrac data generated from \
    parse_dats()

    time_col (str): Column name of the dfs dataframe that specifies time. 

    val_col (str): Column name of the dfs dataframe to be Fourier-transformed.  

    even (bool): If False, will interpolate even sampling. 

    save (bool): If True, will save plots. 
    """

    for animal in range(len(dfs["animal"].unique())):

        df = dfs.loc[dfs["animal"]==animal]

        assert (len(df[time_col] == len(df[val_col]))), \
            "time and val are different lengths! They must be the same."
        assert (time_col in dfs), \
            f"The column, {time_col}, is not in the input dataframe, {dfs}"
        assert (val_col in dfs), \
            f"The column, {val_col}, is not in the input dataframe, {dfs}"

        time = list(df[str(time_col)])
        val = list(df[str(val_col)])


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

        p1, p2 = bokeh_freq_domain(freq, amp)

        p1.title.text = f"frequency domain: animal {animal}"
        p1.title.text_font_size = "16pt"
        p1.yaxis.axis_label_text_font_size = "12pt"
        p2.yaxis.axis_label_text_font_size = "12pt"
        p2.xaxis.axis_label_text_font_size = "12pt"

        output_file(f"fictrac_freqs_{animal}.html", 
                    title=f"fictrac_freqs_{animal}")
        show(gridplot([p1, p2], ncols=1))
        
        # TODO: Add .png and .svg programmatic saving in a subdir--maybe in each FicTrac subdir?

            