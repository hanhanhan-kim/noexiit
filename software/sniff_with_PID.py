#!/usr/bin/env python3

"""
Collect photoionization detector data via the LabJack U3 
DAQ's AIN0 channel.
"""

import datetime
import time
import argparse

import pandas as pd
import matplotlib.pyplot as plt
import u3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("duration", type=float,
        help="Duration (s) of the PID acquisition.")
    args = parser.parse_args()
    
    duration_secs = args.duration
    t_end = time.time() + duration_secs

    times = []
    PID_volts = []

    # For naming output file:
    t_start = datetime.datetime.now().strftime("%m%d%Y_%H%M%S")

    while time.time() <= t_end:

        now = datetime.datetime.fromtimestamp(time.time())
        
        device = u3.U3()
        PID_volt = device.getAIN(0)
        device.close()

        print(f"time: {now}, PID: {PID_volt}")
        
        # Save:
        times.append(now)
        PID_volts.append(PID_volt)


    # Save to file and plot:
    df = pd.DataFrame({"time": times, 
                       "PID_volts": PID_volt})

    df.to_csv(f"PID_volts_{t_start}.csv", 
              index=False)
    
    plt.plot(times, PID_volts)
    plt.show()


if __name__ == "__main__":
    main()