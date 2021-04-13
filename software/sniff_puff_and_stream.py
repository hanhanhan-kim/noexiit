#!/usr/bin/env python3

"""
Commands solenoid valve outputs, while also streaming 
the following 2 types of data to the LabJack U3 DAQ:
  1. Electrical copies of those output commands 
  2. PID data 

By default, the low-voltage pin, FIO7, is hard-coded 
as an analog input on the stream, and is meant to be hooked 
up to the PID signal. 

Example command:
./sniff_puff_and_stream.py ~/tmp/puff_stream.csv 4
"""

import datetime
import time
import argparse
import threading
import atexit
from os.path import expanduser

import pandas as pd
import matplotlib.pyplot as plt
from switchx7 import SwitchX7 
from stream import stream_to_csv


# switch = SwitchX7(port='/dev/ttyACM0', timeout=1.0)
switch = SwitchX7(port='/dev/ttyACM1', timeout=1.0)


def exit_safely():
    switch.set_all(False)
atexit.register(exit_safely)


def control_valves():

    print("1 only: solvent")
    switch.set(0, True)
    switch.set(1, False)
    switch.set(2, False)
    time.sleep(30.0)

    print("2 only: odour")
    switch.set(0, False)
    switch.set(1, True)
    switch.set(2, False)
    time.sleep(10.0) 

    print("1 only: solvent")
    switch.set(1, False)
    switch.set(0, True)
    switch.set(2, False)
    time.sleep(30.0)


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

    # Operate valves: 
    valves_thread = threading.Thread(target=control_valves)
    valves_thread.daemon = True
    valves_thread.start()

    # Start the DAQ stream:
    stream_to_csv(csv_path=csv_path, 
                  duration_s=duration,
                  input_channels=[ # FIOs 4-7 will be LOW voltage AIN on U3-HV
                                    # 3, 
                                    7, 
                                    193, 
                                    # 210, 
                                    # 224
                                 ], 
                  input_channel_names={
                                        # 3: "valve_3", 
                                        7: "PID (V)", 
                                        193: "digi_valves",
                                        # 210: "DAQ count", 
                                        # 224: "16-bit roll-overs"
                                      },
                #   FIO_digital_channels=[4,5,6,8,9,10,11,12,13,14,15], # I don't NEED to specify this; 7 is excluded because it's PID, must be analog 
                  times="absolute",
                  do_overwrite=True, 
                  is_verbose=True)

    

if __name__ == "__main__":
    main()