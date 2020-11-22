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

    times = []
    PID_volts = []
    counts = []

    # Start camera trigger first, and put it in its own thread:
    trig = CameraTrigger("/dev/ttyUSB0")
    connect_sleep_dt = 2.0
    trig.set_freq(100)   # frequency (Hz)
    trig.set_width(10)
    cam_timer = threading.Timer(duration_secs + connect_sleep_dt, trig.stop)
    cam_timer.start()

    # trig.start() only starts recording after a 2.0 s delay, so factor that:
    time.sleep(connect_sleep_dt)

    # Set up DAQ:
    device = u3.U3()
    device.configIO(EnableCounter0=True)

    # For naming output file:
    t_start = datetime.datetime.now().strftime("%m%d%Y_%H%M%S")

    t_end = time.time() + duration_secs
    while time.time() <= t_end:

        now = datetime.datetime.fromtimestamp(time.time())
        PID_volt = device.getAIN(0)
        counter_0_cmd = u3.Counter0(Reset=False)
        count = device.getFeedback(counter_0_cmd)[0] 
        print(f"time: {now}, PID: {PID_volt}, count: {count}")

        # Save:
        times.append(now)
        PID_volts.append(PID_volt)
        counts.append(count)

    device.close()


    # Save to file and plot:
    df = pd.DataFrame({"time": times, 
                       "PID_volts": PID_volt,
                       "count": count})

    df.to_csv(f"PID_volts_{t_start}.csv", index=False)
    
    plt.plot(times, PID_volts)
    plt.show()


if __name__ == "__main__":
    main()