#!/usr/bin/env python3

"""
Batch sorts NOEXIIT rig output files into subdirectories. 
Simplifies batch processing with different analyses. 
"""

import glob
import os
from os.path import join, split, isdir
from shutil import move
import argparse


def main():

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root",
        help="Absolute path to the root directory. I.e. the outermost\
            folder that houses the output files.\
            E.g. /mnt/2TB/data_in/test/")
    parser.add_argument("nesting", type=int,
        help="Specifies the number of folders that are nested from\
            the root directory. I.e. The number of folders between root\
            and the subdirectory that houses the output files. E.g. 1")
    args = parser.parse_args()

    root = args.root
    nesting = args.nesting

    folders = glob.glob(join(root, nesting * "*/"))
    subdirs = ["fictrac/",
               "stimulus/",
               "pose/"]

    for folder in folders:

        assert glob.glob(join(folder, "*.*")), \
            f"The folder {folder} has only subdirectories and no loose files."

        for subdir in subdirs:
            assert not isdir(join(folder, subdir)), \
                f"The folder {subdir} already exists"

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


if __name__ == "__main__":
    main()