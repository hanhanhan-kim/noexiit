#!/usr/bin/env python3

"""
Move the tethered stimulus to each angular position in a list of specified 
positions, while collecting stimulus and camera data.
Upon arriving at a position, extend the tethered stimulus. Remain extended 
for a fixed duration. Then retract the tethered stimulus. Remain retracted 
for the same fixed duration. 
Collect ongoing motor position data as well as photoionization detector data.
In addition, activate an ATMega328P-based camera trigger.
"""

import datetime
import time
import datetime
import sys 
import subprocess
import threading
import atexit
import argparse
from os import rename

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import u3
from autostep import Autostep

from utils import ask_yes_no
from init_BIAS import init_BIAS
from move_and_sniff import home, pt_to_pt_and_poke
from camera_trigger import CameraTrigger


def main():

    # SET UP PARAMETERS-----------------------------------------------------------------------------------------

    # Set up autostep motors, change as necessary:
    motor_port = '/dev/ttyACM0' 
    stepper = Autostep(motor_port)
    stepper.set_step_mode('STEP_FS_128') 
    stepper.set_fullstep_per_rev(200)
    stepper.set_kval_params({'accel':30, 'decel':30, 'run':30, 'hold':30})
    stepper.set_jog_mode_params({'speed':60, 'accel':100, 'decel':1000}) # deg/s and deg/s2
    stepper.set_move_mode_to_jog()
    stepper.set_gear_ratio(1)
    stepper.enable() 

    # Specify BIAS params:
    cam_ports = ['5010', '5020', '5030', '5040', '5050']
    config_path = '/home/platyusa/Videos/bias_behaviour_300hz_1000us.json'

    # TODO: Recall that the duration should match BIAS duration ... ask Will about timing/ordering of trigger duration vs. BIAS duration
    # Set up user arguments:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("duration", type=int,
        help="Duration (s) of the synchronized multi-cam video recordings. If using BIAS, should match the set duration of the BIAS recordings.")
    parser.add_argument("poke_speed", type=int,
        help="A scalar speed factor for the tethered stimulus' extension \
            and retraction. Must be positive. 10 is the fastest. Higher values \
            are slower.")
    parser.add_argument("ext_wait_time", type=float,
        help="Duration (s) for which the tethered stimulus is extended at each \
            set angular position.")
    parser.add_argument("retr_wait_time", type=float,
        help="Duration (s) for which the tethered stimulus is retracted at each \
            set angular position.")
    parser.add_argument("-p", "--posns", nargs="+", type=float, required=True,
        help="A list of angular positions the tethered stimulus will move to. \
            The stimulus will poke and retract at each position in the list. \
            This argument is required.")
    parser.add_argument("-e", "--ext", type=float, default=None, 
        help="The maximum linear servo extension angle. If None, will \
            inherit the value in the `calib_servo.noexiit` file. Default \
            is None.")
    
    args = parser.parse_args()

    duration = args.duration # TODO: incorporate optional duration arg, if not None
    poke_speed = args.poke_speed
    ext_wait_time = args.ext_wait_time
    retr_wait_time = args.retr_wait_time
    posns = args.posns
    ext_angle = args.ext

    assert(poke_speed >= 10), \
        "The poke_speed must be 10 or greater."

    if ext_angle is None:

        with open ("calib_servo.noexiit", "r") as f:
            max_ext = f.read().rstrip('\n')
            
        ext_angle = float(max_ext)
    
    # Set up trigger:
    cam_port = "/dev/ttyUSB0" # TODO: make into an arg?
    trig = CameraTrigger(cam_port) 
    trig.set_freq(100) # frequency (Hz) TODO: make into an arg?
    trig.set_width(10) # (us)
    trig.stop()

    # When script exits, DAQ exits: # TODO: figure out how to trip the SIGINT exit upon p_daq.terminate()

    # When script exits, get_motor_cmds.py stops streaming to csv.

    # When script exits, stop trigger: 
    def stop_trigger():
        print("Stopping trigger ...")
        trig.stop()
        print("Stopped trigger.")
    atexit.register(stop_trigger)

    # When script exits, stop stepper: # TODO: terminate() subprocesses here as well?
    def stop_stepper():
        print("Stopping stepper ...")
        stepper.run(0.0)
        print("Stopped stepper.")
    atexit.register(stop_stepper)

    # EXECUTE--------------------------------------------------------------------------------------------------

    # Initialize BIAS, if desired:
    proceed = ask_yes_no("Initialize BIAS? That is, connect cams, load jsons, and start capture?", default="no")
    if proceed:
        init_BIAS(cam_ports=cam_ports, config_path=config_path)
    else:
        print("Skipping BIAS initialization ...")

    # Home the motors:
    home(stepper)

    # Proceed with experimental conditions once the home is set to 0:
    if stepper.get_position() == 0:

        # Move to first stepper position prior to data acquisition:
        print("Moving to starting stepper position.")
        stepper.move_to(posns[0])
        stepper.busy_wait()
        print("Moved to starting stepper position.")
        
        # START DAQ stream of PID values and counts:
        daq_args = [sys.executable, "count_frames_and_stream.py", "None", cam_port] # sys.executable calls current python
        p_daq = subprocess.Popen(daq_args) 

        # The above process needs AT LEAST a 2.0 s sleep because the required start-up time of the 
        # trigger is 2.0 s, and then the DAQ takes some time to start up. 
        # We want the DAQ to be running BEFORE collecting motor command data, and we want the
        # DAQ to finish AFTER collecting the motor command data, so set this wait to be kind of high
        # to be conservative.
        time.sleep(6.0) 

        t_start = datetime.datetime.now()

        # GET MOTOR positions:
        get_motor_args = [sys.executable, "get_motor_cmds.py", "motor_stream.csv"]
        p_get_motor = subprocess.Popen(get_motor_args)  

        # START TRIGGER:
        trig.start()   

        # START MOTORS:
        pt_to_pt_and_poke(stepper, posns, ext_angle, 
                          poke_speed, ext_wait_time, retr_wait_time) # blocking

        # END THINGS upon completion:
        trig.stop()
        p_get_motor.terminate()
        p_daq.terminate()
          
        
    # SAVE DATA---------------------------------------------------------------------------------------------

    file_ending = t_start.strftime("%Y_%m_%d_%H_%M_%S") + ".csv"

    # Rename the DAQ stream output .csv:
    daq_stream_fname = "o_loop_stream_" + file_ending
    rename("daq_stream.csv", daq_stream_fname) 

    # Rename the motor stream output .csv:
    motor_stream_fname = "o_loop_motor_" + file_ending
    rename("motor_stream.csv", motor_stream_fname)

    # Plot motor commands:
    plt.subplot(2, 1, 1)
    motor_stream_df = pd.read_csv(motor_stream_fname)
    plt.plot(motor_stream_df["datetime"], motor_stream_df["stepper position (deg)"],
             label="stepper position (degs)")
    plt.plot(motor_stream_df["datetime"], motor_stream_df["servo position (deg)"],
             label="servo position (degs)")
    plt.xlabel("time (s)")
    plt.ylabel("motor position (degs)")
    plt.legend()
    plt.grid(True)

    # Plot PID readings:
    plt.subplot(2, 1, 2)
    daq_stream_df = pd.read_csv(daq_stream_fname)
    plt.plot(daq_stream_df["datetime"], daq_stream_df["PID (V)"]) # TODO: can't plot datetime strings
    plt.xlabel("time (s)")
    plt.ylabel("PID reading (V)")
    plt.grid(True)
    plt.savefig(("o_loop_stream_" + file_ending).replace(".csv", ".png"))
    plt.show()

    # Save the stepper settings and servo extension angle: 
    stepper.print_params()
    with open("motor_settings_" + t_start.strftime("%Y_%m_%d_%H_%M_%S") + ".txt", "a") as f:

        print("autostep parameters", file=f)
        print("--------------------------", file=f)
        print('fullstep/rev:  {0}\n'.format(stepper.get_fullstep_per_rev()) +
        'step mode:     {0}\n'.format(stepper.get_step_mode()) +
        'oc threshold:  {0}'.format(stepper.get_oc_threshold()), file=f)
        print('jog mode:', file=f)
        for k,v in stepper.get_jog_mode_params().items():
            print('  {0}: {1} {2}'.format(k,v,Autostep.MoveModeUnits[k]), file=f)
        print('max mode:', file=f)
        for k, v in stepper.get_max_mode_params().items():
            print('  {0}: {1} {2}'.format(k,v,Autostep.MoveModeUnits[k]), file=f)
        print('kvals (0-255): ', file=f)
        for k,v in stepper.get_kval_params().items():
            print('  {0:<6} {1}'.format(k+':',v), file=f)
        # print("\n".join("{}\t{}".format(k, v) for k, v in stepper.get_params().items()), file=f)
        print("\nlinear servo parameters", file=f)
        print("--------------------------", file=f)
        print("max extension angle: %f" %ext_angle, file =f)


if __name__ == "__main__":
    main()