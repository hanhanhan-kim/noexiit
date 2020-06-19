#!/usr/bin/env python3

import sys
import traceback
import datetime
import time
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

import u3

def main():
    
    duration = 60 # secs:
    t_end = time.time() + duration

    while time.time() <= t_end:

        now = datetime.datetime.fromtimestamp(time.time())
        
        device = u3.U3()
        PID_reading = device.getAIN(0)

        print(f"time: {now}, PID: {PID_reading}")
        device.close()

if __name__ == "__main__":
    main()