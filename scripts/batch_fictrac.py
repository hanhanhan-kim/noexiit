#!/usr/bin/env python3

"""
Batch run FicTrac analyses on .avi videos. 
Requires each input .avi to be in a subdirectory called "fictrac". 
"""

import subprocess
import glob
from os.path import join, split, expanduser
import argparse


def main():

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", 
        help="Absolute path to the root directory. I.e. the outermost\
            folder that houses the FicTrac .avi files")
    parser.add_argument("nesting", type=int,
        help="Specifies the number of folders that are nested from the\
            root directory. I.e. the number of folders between root and the\
            'fictrac' subdirectory that houses the input .avi files. E.g. 1.")
    parser.add_argument("fictrac_dir",
        help="Path to the FicTrac source directory. Accepts tilde.\
             E.g. ~/src/fictrac/")
    parser.add_argument("config_path",
        help="Absolute path to the configuration file for FicTrac analyses.\
             E.g. /mnt/2TB/data_in/HK_20200316/config_fictrac.txt")
    args = parser.parse_args()

    root = args.root
    nesting = args.nesting
    vids = sorted(glob.glob(join(root, nesting * "*/", "fictrac/*.avi")))

    fictrac_dir = expanduser(args.fictrac_dir)
    fictrac_executable = join(fictrac_dir, "bin/fictrac")

    config_path = args.config_path

    for vid in vids:

        # Specify fictrac vid to src_fn:
        with open(config_path, "r") as f:
            config = f.readlines()

        new_lines = []
        for line in config:

            if line.startswith("src_fn"):
                line = f"src_fn: {vid}\n"

            new_lines.append(line)

        with open(config_path, "w") as f:
            f.writelines(new_lines)

        # Run fictrac:
        fictrac_dir = split(vid)[0]
        args = [fictrac_executable, config_path]
        equivalent_cmd = ' '.join(args)
        print(f'running command {equivalent_cmd} from dir {fictrac_dir}')
        subprocess.run(args, cwd=fictrac_dir)


if __name__ == "__main__":
    main()