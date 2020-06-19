#!/usr/bin/env python3

import datetime
import time
import pandas as pd
import matplotlib.pyplot as plt

import u3

def main():

    duration_secs = 10 
    t_end = time.time() + duration_secs

    times = []
    PID_volts = []

    # For naming output file:
    t_start = datetime.datetime.now().strftime("%m%d%Y_%H%M%S")

    while time.time() <= t_end:

        now = datetime.datetime.fromtimestamp(time.time())
        
        device = u3.U3()
        PID_volt = device.getAIN(0)

        print(f"time: {now}, PID: {PID_volt}")
        times.append(now)
        PID_volts.append(PID_volt)

        device.close()

    # Save data to file and plot:
    df = pd.DataFrame({"time": times, 
                       "PID_volts": PID_volt})

    df.to_csv(f"PID_volts_{t_start}.csv", 
              index=False)
    
    plt.plot(times, PID_volts)
    plt.show()

if __name__ == "__main__":
    main()