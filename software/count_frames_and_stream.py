#!/usr/bin/env python3

"""
Demos U3-HV's counter function. 
Counts digital inputs into the FIO4 pin. 
Useful for counting hardware trigger outputs to cams (i.e. frames)
"""

import datetime
import time
import argparse
import threading

import pandas as pd
import matplotlib.pyplot as plt
from camera_trigger import CameraTrigger
from stream import stream_to_csv


def main():

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("duration", type=float,
        help="Duration (s) of the PID acquisition.")
    args = parser.parse_args()
    
    duration = args.duration

    # Start the DAQ stream and cam trigger:
    stream_to_csv("test.csv", 
                duration_s=duration,
                input_channels=[0, 210, 224], 
                input_channel_names={0: "PID", 210: "DAQ count", 224: "TC_Capture"},
                external_trigger={"port":"/dev/ttyUSB0", "freq":100, "width":10},
                do_overwrite=True, 
                is_verbose=False)


if __name__ == "__main__":
    main()