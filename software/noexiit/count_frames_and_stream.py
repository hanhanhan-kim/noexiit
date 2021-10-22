#!/usr/bin/env python3

"""
Demos simultaneous cam trigger initiation, and analog streaming 
and counting on the U3-HV,  
Streams analog inputs into the AIN0 pin, and counts digital 
inputs into the FIO4 pin (Counter0).

Example command:
./count_frames_and_stream.py stream.csv 5 
"""

import datetime
import time
import argparse
import threading
from os.path import expanduser

import pandas as pd
import matplotlib.pyplot as plt
from camera_trigger import CameraTrigger
from stream import stream_to_csv


def main():

    parser = argparse.ArgumentParser(description=__doc__, 
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_path", 
        help="Path to which to stream the .csv. Saves during acquisition.")
    parser.add_argument("duration",
        help="Duration (s) of the DAQ stream. If None, will stream until exited (ctrl+c).")
    args = parser.parse_args()
    
    csv_path = expanduser(args.csv_path)
    duration = args.duration

    # TODO : Don't run more than one counter and/or timer. The required multiple 224 
    # channels means I have to make some fixes.
    # See: https://labjack.com/support/datasheets/u3/operation/stream-mode/digital-inputs-timers-counters

    if duration.lower() == "none":
        duration = None
    else:
        duration = float(duration)

    assert csv_path.endswith(".csv"), f"{csv_path} is not a .csv file"

    # Start the DAQ stream and cam trigger:
    stream_to_csv(csv_path=csv_path, 
                  duration_s=duration,
                  input_channels=[0, 210, 224], # 7 is an FIO, and so will be LOW voltage on U3-HV
                  input_channel_names={0: "PID (V)", 210: "DAQ count", 224: "16-bit roll-overs"},
                  times="absolute",
                  external_trigger={"port":"/dev/ttyUSB0", "freq":100, "width":10},
                  do_overwrite=True, 
                  is_verbose=True)


if __name__ == "__main__":
    main()