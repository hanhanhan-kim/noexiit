#!/usr/bin/env python3

from __future__ import print_function

import time
import atexit
import numpy as np
import matplotlib.pyplot as plt

from autostep import Autostep


def stop_stepper(dev):
    """
    A wrapper function that stops the motor when the script exits. 

    dev: Autostep object
    """
    dev.run(0.0)


def main():

    dev.move_to(354.963)
    dev.busy_wait()
    dev.set_position(0)

    dev.clear_sensor_calibration()
    dev.calibrate_sensor(360)
    dev.save_sensor_calibration("sensor_calibration.txt")


if __name__ == "__main__":

    port = '/dev/ttyACM0'

    dev = Autostep(port)
    dev.set_step_mode('STEP_FS_64') 
    dev.set_fullstep_per_rev(200)
    dev.set_gear_ratio(1.0)

    dev.set_jog_mode_params({'speed': 200,  'accel': 1000, 'decel': 1000})
    dev.set_max_mode_params({'speed': 1000,  'accel': 30000, 'decel': 30000})
    dev.set_move_mode_to_jog()

    dev.print_params()

    main()

    