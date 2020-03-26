#!/usr/bin/env python3

import subprocess
import glob
from os.path import join, split, expanduser


root = "/mnt/2TB/data_in/HK_20200316/"
vids = sorted(glob.glob(join(root, "*/fictrac/*.avi")))

fictrac_dir = expanduser("~/src/fictrac")
fictrac_executable = join(fictrac_dir, "bin/fictrac")

config_dir = "/mnt/2TB/data_in/HK_20200316/"
config_fname = join(config_dir, "config_fictrac.txt")

for vid in vids:

    # Specify fictrac vid to src_fn:
    with open(config_fname, "r") as f:
        config = f.readlines()
        # import pprint; pprint.pprint(config)

    new_lines = []
    for line in config:

        if line.startswith("src_fn"):
            line = f"src_fn: {vid}\n"

        new_lines.append(line)
    # pprint.pprint(new_lines)
    # import ipdb; ipdb.set_trace()

    with open(config_fname, "w") as f:
        f.writelines(new_lines)

    # Run fictrac:
    fictrac_dir = split(vid)[0]
    args = [fictrac_executable, config_fname]
    equivalent_cmd = ' '.join(args)
    print(f'running command {equivalent_cmd} from dir {fictrac_dir}')
    subprocess.run(args, cwd=fictrac_dir)