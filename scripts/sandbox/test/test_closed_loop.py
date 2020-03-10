#!/usr/bin/env python3

import pytest
import numpy as np

import closed_loop as c

def test_angular_diff_rad():

    a0_degs = [15, -350]
    a1_degs = [20, 10]
    correct_diffs_deg = [5, 20]
    for a0_deg, a1_deg, correct_diff_deg in zip(a0_degs, a1_degs, correct_diffs_deg):
        a0_rad = np.deg2rad(a0_deg)
        a1_rad = np.deg2rad(a1_deg)
        
        wrapped_diff_rad = c.angular_diff_rad(a0_rad, a1_rad)
        print('wrapped_diff_rad:', wrapped_diff_rad)

        wrapped_diff_deg = np.rad2deg(wrapped_diff_rad)
        print('wrapped_diff_deg:', wrapped_diff_deg)
        print(np.isclose(correct_diff_deg, wrapped_diff_deg))
        assert np.isclose(correct_diff_deg, wrapped_diff_deg)
