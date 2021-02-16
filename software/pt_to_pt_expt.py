#!/usr/bin/env python3

"""
Moves the tethered stimulus to each angular position in a list of specified 
positions. Upon arriving at a position, extends the tethered stimulus for a fixed
duration. Then retracts the tethered stimulus for a fixed duration.

Collects and saves, but does not stream, data during motor movements.
Data includes PID inputs, trigger counts, and motor positions. 
Does not support interrupted recordings.
Motor position sets and gets and DAQ gets happen in the same proces which 
throttles, the frequencies. 

Example command:
./pt_to_pt_expt.py 20 10 2 2 -p 180 0 -e 90
"""

from autostep import Autostep
import datetime
import time
import datetime
import threading
import atexit
import argparse

import yaml
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import u3

import utils
import move_and_get
from camera_trigger import CameraTrigger
from init_BIAS import init_BIAS
from move_and_get import home, pt_to_pt_and_poke

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

    # Specify external cam trigger params:
    trig_port = "/dev/ttyUSB0"

    # TODO: Recall that the duration should match BIAS duration ... ask Will about timing/ordering of trigger duration vs. BIAS duration
    # Set up user arguments:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("duration", type=int,
        help="Duration (s) of the synchronized multi-cam video recordings.")
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
            inherit the value in the `config.yaml` file. Default is None.")
    
    args = parser.parse_args()

    duration = args.duration
    poke_speed = args.poke_speed
    ext_wait_time = args.ext_wait_time
    retr_wait_time = args.retr_wait_time
    posns = args.posns
    ext_angle = args.ext

    if poke_speed < 10:
        raise ValueError("The poke_speed must be 10 or greater.")

    if ext_angle is None:
        with open("config.yaml") as f:
            ext_angle = yaml.load(f, Loader=yaml.FullLoader)["max_ext"]

    # Set up filename to save:
    t_script_start = datetime.datetime.now()
    name_script_start = t_script_start.strftime("%Y_%m_%d_%H_%M_%S")
    with open ("config.yaml") as f:
        output_dir = yaml.load(f, Loader=yaml.FullLoader)["output_dir"]

    # Save the motor settings: 
    fname = f"motor_settings_{name_script_start}.txt"
    servo_msg = f"\nlinear servo parameters \n-------------------------- \nmax extension angle: {ext_angle}\n"
    move_and_get.save_params(stepper, fname)
    # Write:
    with open(fname, "a") as f:
        print(servo_msg, file=f)
    # Print:
    with open(fname) as f:
        print(f.read())
    
    # Stop the stepper when script is killed:
    def stop_stepper():
        stepper.run(0.0)
    atexit.register(stop_stepper)

    # EXECUTE--------------------------------------------------------------------------------------------------

    # Initialize BIAS, if desired:
    proceed = utils.ask_yes_no("Initialize BIAS? That is, connect cams, load jsons, and start capture?", default="no")
    if proceed:
        init_BIAS(cam_ports=cam_ports, config_path=config_path)
    else:
        print("Skipping BIAS initialization ...")

    # Home the motors:
    home(stepper)

    # Proceed with experimental conditions once the home is set to 0:
    if stepper.get_position() == 0:

        cal_times = []
        elapsed_times = []
        counts = []
        PID_volts = []
        stepper_posns = []
        servo_posns = []

        # Set up DAQ:
        device = u3.U3()

        # Make motor thread:
        motors_thread = threading.Thread(target=pt_to_pt_and_poke, 
                                         args=(stepper, posns, ext_angle, poke_speed,
                                               ext_wait_time, retr_wait_time))
        
        # Move to first stepper position prior to data acquisition:
        stepper.move_to(posns[0])
        stepper.busy_wait()
        
        # Set up cam trigger:
        trig = CameraTrigger(trig_port)
        trig.set_freq(100) # frequency (Hz)
        trig.set_width(10)
        trig.stop() # trig tends to continue running from last time

        # Initializing the camera trigger takes 2.0 secs:
        time.sleep(2.0)

        # Make a thread to stop the cam trigger after some time:
        cam_timer = threading.Timer(duration, trig.stop)
        
        # START the DAQ counter, 1st count pre-trigger is 0:
        u3.Counter0(Reset=True)
        device.configIO(EnableCounter0=True)
        print(f"First count is pre-trigger and is 0: {device.getFeedback(u3.Counter0(Reset=False))[0]}")
        time.sleep(2.0) # give time to see above print

        # START the motors, the trigger, and the trigger-stopping timer:
        motors_thread.start()
        trig.start()
        cam_timer.start()

        # Get data while cam trigger is active:
        t_start = datetime.datetime.now()
        while cam_timer.is_alive(): 
            
            now = datetime.datetime.now()
            elapsed_time = (now - t_start).total_seconds() # get timedelta obj

            counter_0_cmd = u3.Counter0(Reset=False)
            count = device.getFeedback(counter_0_cmd)[0] # 1st count post-trigger is 1

            PID_volt = device.getAIN(0)
            stepper_posn = stepper.get_position()
            servo_posn = stepper.get_servo_angle()

            print(f"Calendar time: {now}\n", 
                  f"Elapsed time (s): {elapsed_time}\n", 
                  f"Count (frame): {count}\n",
                  f"PID (V): {PID_volt}\n",
                  f"Stepper position (deg): {stepper_posn}\n", 
                  f"Servo position (deg): {servo_posn}\n\n") 

            # Save:
            cal_times.append(now)
            elapsed_times.append(elapsed_time)
            counts.append(count)
            PID_volts.append(PID_volt)
            stepper_posns.append(stepper_posn)
            servo_posns.append(servo_posn)

        # Close DAQ: 
        device.close()

        # Join the motors thread back to the main:
        motors_thread.join()

        # SAVE DATA---------------------------------------------------------------------------------------------

        # Save outputs, except elapsed times, to a csv:
        df = pd.DataFrame({ "Calendar time": cal_times,
                            "DAQ count": counts,
                            "PID (V)": PID_volts,
                            "Stepper position (deg)": stepper_posns,
                            "Servo position (deg)": servo_posns})
        df.to_csv(f"{output_dir}o_loop_{name_script_start}.csv", index=False)

        # Plot:
        plt.style.use("ggplot")

        ax1 = plt.subplot(2, 1, 1)
        ax1.tick_params(labelbottom=False) 
        plt.plot(elapsed_times, stepper_posns,
                 label="stepper position (degs)")
        plt.plot(elapsed_times, servo_posns,
                 label="servo position (degs)")
        plt.ylabel("motor position (degs)")
        plt.legend()
        plt.grid(True)

        ax2 = plt.subplot(2, 1, 2, sharex=ax1)
        plt.plot(elapsed_times, PID_volts)
        plt.xlabel("time (s)")
        plt.ylabel("PID reading (V)")
        plt.grid(True)
        
        plt.subplots_adjust(hspace=.1)

        plt.savefig(f"{output_dir}o_loop_{name_script_start}.png", dpi=500)
        plt.show()


if __name__ == "__main__":
    main()