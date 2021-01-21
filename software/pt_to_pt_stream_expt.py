#!/usr/bin/env python3

"""
TODO: ** Explain how this code works, and the order of starting events and exits. **
TODO: ** Implement SIGINT exit conditions for main process events (i.e. not the DAQ). **
TODO: ** Incorporate set duration of recording (which might be shorter or longer than
the length of motor events.)
"""

import datetime
import time
import datetime
import sys 
import subprocess
import threading
import atexit
import signal
import argparse
import os

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import u3
from autostep import Autostep

from utils import ask_yes_no
from init_BIAS import init_BIAS
import move_and_get
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
        help="Duration (s) of the synchronized multi-cam video recordings. \
            If using BIAS, should match the set duration of the BIAS recordings.")
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
    parser.add_argument("-e", "--ext", type=int, default=None, 
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

    if poke_speed < 10:
        raise ValueError("The poke_speed must be 10 or greater.")

    if ext_angle is None:
        with open ("calib_servo.noexiit", "r") as f:
            max_ext = f.read().rstrip('\n')
        ext_angle = int(max_ext)
    
    # Set up filename to save:
    t_script_start = datetime.datetime.now()
    file_ending = t_script_start.strftime("%Y_%m_%d_%H_%M_%S") + ".csv"

    # Save the motor settings: 
    fname = "motor_settings_" + t_script_start.strftime("%Y_%m_%d_%H_%M_%S") + ".txt"
    servo_msg = f"\nlinear servo parameters \n-------------------------- \nmax extension angle: {ext_angle}\n"
    move_and_get.save_params(stepper, fname)
    # Write:
    with open(fname, "a") as f:
        print(servo_msg, file=f)
    # Print:
    with open(fname) as f:
        print(f.read())
    
    # Set up thread for getting motor commands;
    # (can't be a subprocess, because I can create only one Autostep object):
    get_motors_thread = threading.Thread(target=move_and_get.stream_to_csv, 
                                         args=(stepper, f"o_loop_motor_{file_ending}"))

    # Set up trigger:
    trigger_port = "/dev/ttyUSB0" # TODO: make into an arg?
    trig = CameraTrigger(trigger_port) 
    trig.set_freq(100) # frequency (Hz) TODO: make into an arg?
    trig.set_width(10) # (us)
    trig.stop()

    # Initializing the CameraTrigger takes 2.0 secs:
    print("Initializing the external trigger ...")
    time.sleep(2.0)
    print("Initialized external trigger.")

    # TODO: Put the two below atexit fxns on SIGINT only,
    # so it's not redundant with a normal exit. 

    # # When script exits, stop trigger: 
    # def stop_trigger():
    #     print("Stopping external trigger ...")
    #     trig.stop()
    #     print("Stopped external trigger.")
    # atexit.register(stop_trigger)

    # # When script exits, stop stepper:
    # def stop_stepper():
    #     print("Stopping stepper ...")
    #     stepper.run(0.0)
    #     print("Stopped stepper.")
    # atexit.register(stop_stepper)

    # EXECUTE--------------------------------------------------------------------------------------------------

    # Initialize BIAS, if desired:
    proceed = ask_yes_no("Initialize BIAS? That is, connect cams, load jsons, and start capture?", default="no")
    if proceed:
        init_BIAS(cam_ports=cam_ports, config_path=config_path)
    else:
        print("Skipping BIAS initialization ...")

    # Home the motors:
    move_and_get.home(stepper)

    # Proceed with experimental conditions once the home is set to 0:
    if stepper.get_position() == 0:

        # Move to first stepper position prior to data acquisition:
        print("Moving to starting stepper position.")
        stepper.move_to(posns[0])
        stepper.busy_wait()
        print("Moved to starting stepper position.")
        
        # START DAQ stream of PID values and counts (trigger not called here):
        daq_args = [sys.executable, # sys.executable calls current python
                    "stream.py", f"o_loop_stream_{file_ending}", "none", "absolute"] 
        p_daq = subprocess.Popen(daq_args) 
        time.sleep(1.0) # DAQ start-up takes a bit

        # GET MOTOR positions :
        get_motors_thread.start()  
        time.sleep(0.1) # Make sure not to start after the trigger

        # START TRIGGER:
        print("Starting external trigger ...")
        trig.start()   
        print("Started external trigger.")

        # START MOTORS (is blocking):
        move_and_get.pt_to_pt_and_poke(stepper, posns, ext_angle, 
                                       poke_speed, ext_wait_time, retr_wait_time)

        # STOP EVERYTHING upon completion:
        print("Stopping external trigger ...")
        trig.stop()
        print("Stopped external trigger.")
        print("Stopping the motor commands stream to csv ...")
        move_and_get._getting_motors = False
        get_motors_thread.join() 
        print("Stopped the motor command stream to csv.")
        print("Stopping the DAQ stream process ...")
        # DAQ process must die on SIGINT to exit correctly:
        os.kill(p_daq.pid, signal.SIGINT) 
        time.sleep(1.0) # Sleep for a bit so the exit prints come out in the right order
        if not p_daq.poll():
            print("Stopped the DAQ stream process.")
        
    # SAVE DATA---------------------------------------------------------------------------------------------

    # TODO: can't plot datetime strings ... convert to datetime or float

    # # Plot motor commands:
    # plt.subplot(2, 1, 1)
    # motor_stream_df = pd.read_csv(motor_stream_fname)
    # plt.plot(motor_stream_df["datetime"], motor_stream_df["stepper position (deg)"],
    #          label="stepper position (degs)")
    # plt.plot(motor_stream_df["datetime"], motor_stream_df["servo position (deg)"],
    #          label="servo position (degs)")
    # plt.xlabel("time (s)")
    # plt.ylabel("motor position (degs)")
    # plt.legend()
    # plt.grid(True)

    # # Plot PID readings:
    # plt.subplot(2, 1, 2)
    # daq_stream_df = pd.read_csv(daq_stream_fname)
    # plt.plot(daq_stream_df["datetime"], daq_stream_df["PID (V)"]) 
    # plt.xlabel("time (s)")
    # plt.ylabel("PID reading (V)")
    # plt.grid(True)
    # plt.savefig(("o_loop_stream_" + file_ending).replace(".csv", ".png"))
    # plt.show()


if __name__ == "__main__":
    main()