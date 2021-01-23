#!/usr/bin/env python3

"""
Demos simultaneous analog command-response and counting on the U3-HV. 
Gets analog inputs into the AIN0 pin, and counts digital inputs into 
the FIO4 pin (Counter0).
Does not support infinite or interrupted recordings. 

Example command:
./count_frames_and_sniff.py cmd_rsp.csv 5
"""

import datetime
import time
import argparse
import threading

import pandas as pd
import matplotlib.pyplot as plt
import u3
from camera_trigger import CameraTrigger


def main():

    parser = argparse.ArgumentParser(description=__doc__, 
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_path", 
        help="Path to which to save the .csv. Does not save during acquisition.")
    parser.add_argument("duration", type=float,
        help="Duration (s) of the DAQ recording.")
    args = parser.parse_args()
    
    csv_path = args.csv_path
    duration = args.duration

    cal_times = []
    PID_volts = []
    counts = []

    # Set up DAQ:
    device = u3.U3()

    # Set up cam trigger:
    trig = CameraTrigger("/dev/ttyUSB0")
    trig.set_freq(100) # frequency (Hz)
    trig.set_width(10)
    trig.stop() # trig tends to continue running from last time

    # Initializing the CameraTrigger takes 2.0 secs:
    print("Initializing the external trigger ...")
    time.sleep(2.0)

    # Set up a timer in its own thread, to end the cam trigger:
    cam_timer = threading.Timer(duration, trig.stop)

    # Start the DAQ counter:
    u3.Counter0(Reset=True)
    device.configIO(EnableCounter0=True)
    print(f"First count is pre-trigger and is 0: {device.getFeedback(u3.Counter0(Reset=False))[0]}")
    time.sleep(1.0) # give time to see above print

    # Start the trigger, and its timer to stop it:
    trig.start()
    cam_timer.start()

    t_start = datetime.datetime.now()
    t_end = time.time() + duration
    while time.time() <= t_end:

        now = datetime.datetime.now()
        PID_volt = device.getAIN(0)
        counter_0_cmd = u3.Counter0(Reset=False)
        count = device.getFeedback(counter_0_cmd)[0] 
        print(f"time: {now}, PID: {PID_volt}, count: {count}")

        # Save:
        cal_times.append(now)
        PID_volts.append(PID_volt)
        counts.append(count)

    device.close()

    # Save to file and plot:
    df = pd.DataFrame({"Calendar time": cal_times,
                       "PID (V)": PID_volts,
                       "DAQ count": counts})

    # t_start  = t_start.strftime("%m%d%Y_%H%M%S")
    df.to_csv(csv_path, index=False)
    
    plt.plot(cal_times, PID_volts)
    plt.show()


if __name__ == "__main__":
    main()