#!/usr/bin/env python3

import glob
import os
from os.path import join, split
from shutil import move


# Change root as needed:
root = "/mnt/2TB/data_in/HK_20200317/"

# How many folders are nested from root?
nesting = 1

folders = glob.glob(join(root, nesting * "*/"))
subdirs = ["fictrac/",
           "stimulus/",
           "pose/"]

for folder in folders:

    # Make my subdirs:
    [os.mkdir(join(folder, subdir)) for subdir in subdirs]

    # Put videos in corresponding subdirs:
    fmfs = glob.glob(join(folder, "*.fmf"))
    avis = glob.glob(join(folder, "*.avi"))
    vids = fmfs + avis

    for vid in vids:
        # This digit string is the FicTrac cam serial no.
        if "18475996" in vid:
            move(vid, join(folder, "fictrac/"))
        else:
            move(vid, join(folder, "pose/"))

    # Put non-vid files into stimulus subdir:
    nonvids = glob.glob(join(folder, "*"))
    for nonvid in nonvids:
        if "motor" in nonvid:
            move(nonvid, join(folder, "stimulus/"))