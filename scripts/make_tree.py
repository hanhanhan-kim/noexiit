#!/usr/bin/env python3

import glob
import os
from os.path import join, split
from shutil import move


# root = "/mnt/2TB/data_in/HK_20200317/"
root = "/mnt/2TB/data_in/test/"

folders = glob.glob(join(root, "*/"))
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
        if "18475996" in vid:
            move(vid, join(folder, "fictrac/"))
        else:
            move(vid, join(folder, "pose/"))

    # Put non-vid files into stimulus subdir:
    nonvids = glob.glob(join(folder, "*"))
    for nonvid in nonvids:
        if "motor" in nonvid:
            move(nonvid, join(folder, "stimulus/"))