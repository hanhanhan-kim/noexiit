#!/usr/bin/env python3

"""
Demos simultaneous streaming and counting on the U3-HV. 
Counts digital inputs into the FIO4 pin (Counter0).
Useful for counting hardware trigger outputs to cams (i.e. frames).
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
    parser.add_argument("duration",
        help="Duration (s) of the PID acquisition. If None, will stream until exited (ctrl+c).")
    parser.add_argument("port",
        help="Path to the ATMega328P trigger's port, e.g. /dev/ttyUSB0")
    args = parser.parse_args()
    
    duration = args.duration
    port = args.port

    # TODO : Don't run more than one counter and/or timer. The required multiple 224 
    # channels means I have to make some fixes.
    # See: https://labjack.com/support/datasheets/u3/operation/stream-mode/digital-inputs-timers-counters

    if duration.lower() == "none":
        duration = None
    else:
        duration = float(duration)

    # Start the DAQ stream and cam trigger:
    stream_to_csv("stream.csv", 
                duration_s=duration,
                input_channels=[0, 210, 224], 
                input_channel_names={0: "PID (V)", 210: "DAQ count", 224: "16-bit roll-overs"},
                times="absolute",
                external_trigger={"port":port, "freq":100, "width":10},
                do_overwrite=True, 
                is_verbose=True)


if __name__ == "__main__":
    main()