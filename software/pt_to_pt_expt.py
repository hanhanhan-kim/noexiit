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

from __future__ import print_function
from autostep import Autostep
import datetime
import time
import datetime
import threading
import atexit
import argparse

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import u3

from camera_trigger import CameraTrigger
from init_BIAS import init_BIAS
from move_and_sniff import home, pt_to_pt_and_poke

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
            inherit the value in the `calib_servo.noexiit` file. Default \
            is None.")
    
    args = parser.parse_args()

    duration = args.duration
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
    
    # Stop the stepper when script is killed:
    def stop_stepper():
        stepper.run(0.0)
    atexit.register(stop_stepper)

    # EXECUTE--------------------------------------------------------------------------------------------------

    # Initialize BIAS, if desired:
    # TODO: Make this less shitty, default to N
    # Remember
    while True:
        proceed = input("Initialize BIAS? That is, connect cams, load jsons, and start capture? Input y or n: \n")
        if proceed == "y":
            init_BIAS(cam_ports = cam_ports,
                      config_path = config_path)
            break
        elif proceed == "n":
            print("Skipping BIAS initialization ...")
            break
        else:
            print("Please input y or n.")
            time.sleep(1.0)
            continue

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
        
        # Set up cam trigger:
        trig = CameraTrigger(trig_port)
        trig.set_freq(100) # frequency (Hz)
        trig.set_width(10)

        # Initializing the camera trigger takes 2.0 secs:
        time.sleep(2.0)

        # Make a thread to stop the cam trigger after some time:
        cam_timer = threading.Timer(duration, trig.stop)

        # START the DAQ counter:
        device.configIO(EnableCounter0=True) 
        print(f"First count is pre-trigger and should be 0: {device.getFeedback(u3.Counter0(Reset=False))[0]}")
        u3.Counter0(Reset=True)

        # START the motors, the trigger, and the trigger-stopping timer:
        motors_thread.start()
        trig.start()
        cam_timer.start()

        # Get data while motors are active:
        t_start = datetime.datetime.now()
        while cam_timer.is_alive() == True: # TODO: change to while cam_timer is alive?
            
            now = datetime.datetime.now()
            elapsed_time = (now - t_start).total_seconds() # get timedelta obj

            counter_0_cmd = u3.Counter0(Reset=False)
            count = device.getFeedback(counter_0_cmd)[0] 

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

        # Save outputs to a csv:
        df = pd.DataFrame({ "Calendar time": cal_times,
                            "Elapsed time (s)": elapsed_times,
                            "Count (frame)": counts,
                            "PID (V)": PID_volts,
                            "Stepper position (deg)": stepper_posns,
                            "Servo position (deg)": servo_posns})

        df.to_csv(t_start.strftime("%m%d%Y_%H%M%S") + '_motor_commands.csv', index=False)

        # Plot motor commands:
        plt.subplot(2, 1, 1)
        plt.plot(elapsed_times, stepper_posns,
                 label="stepper position (degs)")
        plt.plot(elapsed_times, servo_posns,
                 label="servo position (degs)")
        plt.xlabel("time (s)")
        plt.ylabel("motor position (degs)")
        plt.legend()
        plt.grid(True)

        # Plot PID readings:
        plt.subplot(2, 1, 2)
        plt.plot(elapsed_times, PID_volts)
        plt.xlabel("time (s)")
        plt.ylabel("PID reading (V)")
        plt.grid(True)
        plt.savefig(t_start.strftime("%m%d%Y_%H%M%S") + '_motor_commands.png')
        plt.show()

        # Save the stepper settings and servo extension angle: 
        stepper.print_params()
        with open(t_start.strftime("%m%d%Y_%H%M%S") + "_motor_settings.txt", "a") as f:

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