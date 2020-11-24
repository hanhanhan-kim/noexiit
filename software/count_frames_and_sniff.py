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
import u3
from camera_trigger import CameraTrigger


def main():

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("duration", type=float,
        help="Duration (s) of the PID acquisition.")
    args = parser.parse_args()
    
    duration_secs = args.duration

    cal_times = []
    PID_volts = []
    counts = []

    # Set up DAQ:
    device = u3.U3()

    # Set up cam trigger:
    trig = CameraTrigger("/dev/ttyUSB0")
    trig.set_freq(100) # frequency (Hz)
    trig.set_width(10)

    # Initializing the CameraTrigger takes 2.0 secs:
    time.sleep(2.0)

    # Set up a timer in its own thread, to end the cam trigger:
    cam_timer = threading.Timer(duration_secs, trig.stop)

    # Start the DAQ counter:
    u3.Counter0(Reset=True)
    device.configIO(EnableCounter0=True)
    print(f"First count, pre-trigger: {device.getFeedback(u3.Counter0(Reset=False))[0]}")

    # Start the trigger, and its timer to stop it:
    trig.start()
    cam_timer.start()

    t_start = datetime.datetime.now()
    t_end = time.time() + duration_secs
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
                       "Count": counts})

    t_start  = t_start.strftime("%m%d%Y_%H%M%S")
    df.to_csv(f"PID_volts_{t_start}.csv", index=False)
    
    plt.plot(cal_times, PID_volts)
    plt.show()


if __name__ == "__main__":
    main()