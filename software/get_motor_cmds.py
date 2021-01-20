#!/usr/bin/env python3

"""
"""

import datetime
import argparse
import atexit
import csv
import sys
from pathlib import Path

import pandas as pd
from autostep import Autostep


def stream_to_csv(stepper, csv_path):
            
    """
    Saves motor commands to csv.
    
    Parameters:
    -----------
    stepper (Autostep): The Autostep object, defined with the correct port. 
        E.g. Autostep("/dev/ttyACM0")
        Do NOT make this object more than once. 
    csv_path (str): Path to which to stream the .csv.

    """

    # TODO: add overwrite handling
    # TODO: add support for break conditions, e.g. after some duration of recording

    column_names = ["datetime", "stepper position (deg)", "servo position (deg)"]

    if sys.version_info >= (3, 0):
        open_kwargs = dict(newline="")
    else:
        open_kwargs = dict()

    csv_file_handle = open(csv_path, "w", **open_kwargs)
    
    # When script exits, stop streaming to csv:
    def close_csv_handle():
        print("Closing .csv handle ...")
        csv_file_handle.close()
        print("Closed .csv handle.")
    atexit.register(close_csv_handle)

    csv_writer = csv.DictWriter(csv_file_handle, fieldnames=column_names)
    csv_writer.writeheader()
    
    while True:

        now = datetime.datetime.now()
        stepper_posn = stepper.get_position()
        servo_posn = stepper.get_servo_angle()

        print(f"{column_names[0]}: {now}\n", 
              f"{column_names[1]}: {stepper_posn}\n", 
              f"{column_names[2]}: {servo_posn}\n\n") 

        csv_writer.writerow({column_names[0]: now, 
                             column_names[1]: stepper_posn, 
                             column_names[2]: servo_posn})


def main():
    
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", 
        help="Path to which to stream the .csv.")
    args = parser.parse_args()
    
    csv_path = args.csv_path

    # Set up Autostep motors, change as necessary: 
    motor_port = '/dev/ttyACM0' 
    stepper = Autostep(motor_port)
    stepper.set_step_mode('STEP_FS_128') 
    stepper.set_fullstep_per_rev(200)
    stepper.set_kval_params({'accel':30, 'decel':30, 'run':30, 'hold':30})
    stepper.set_jog_mode_params({'speed':60, 'accel':100, 'decel':1000}) # deg/s and deg/s2
    stepper.set_move_mode_to_jog()
    stepper.set_gear_ratio(1)
    stepper.enable()

    stream_to_csv(stepper, csv_path)


if __name__ == "__main__":
    main()