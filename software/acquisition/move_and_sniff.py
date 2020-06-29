#!/usr/bin/env python3

"""
Move the tethered stimulus to each angular position in a list of specified 
positions.
Upon arriving at a position, extend the tethered stimulus. Remain extended 
for a fixed duration. Then retract the tethered stimulus. Remain retracted 
for the same fixed duration. 
Collect ongoing motor position data as well as photoionization detector data.
"""

from __future__ import print_function
from autostep import Autostep
import time
import datetime
import threading
import argparse

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import u3


def pt_to_pt_and_poke(stepper, posns, ext_angle, poke_speed, 
                      ext_wait_time, retr_wait_time):
    
    '''
    Specifies stepper motor and servo motor behaviours according to a 
    list of target positions. 

    Parameters:
    -----------
        stepper (Autostep obj): The Autostep object, defined with respect 
            to the correct port. Do NOT make this object more than once.

        posns (list): List of target absolute positions to move to.

        ext_angle (float): The linear servo's extension 'angle' for full 
            extension.

        poke_speed (int): A scalar speed factor for the tethered stimulus' 
            extension and retraction. Must be positive. 10 is the fastest. 
            Higher values are slower. 

        ext_wait_time (float): Duration (s) for which the tethered stimulus 
            is extended at each set angular position. 

        retr_wait_time (float): Duration (s) for which the tethered stimulus
            is retracted at each set angular position. 

    Returns:
    --------
    Moves motors to specified positions with wait times. 
    '''

    assert(poke_speed >= 10), \
        "The `poke_speed` must be 10 or greater."

    fwd_angles = list(np.linspace(0, ext_angle, int(poke_speed)))
    rev_angles = list(fwd_angles[::-1])
    dt = 0.01

    for pos in posns:
        # Move stepper to pos:
        stepper.move_to(pos)
        stepper.busy_wait()
        # Extend linear servo:
        for angle in fwd_angles:
            stepper.set_servo_angle(angle)
            while stepper.get_servo_angle() <= ext_angle is True:
                time.sleep(dt)
        # Wait at extension:
        time.sleep(ext_wait_time)
        # Retract linear servo:
        for angle in rev_angles:
            stepper.set_servo_angle(angle)
            while stepper.get_servo_angle() >= 0 is True:
                time.sleep(dt)
        # Wait at retraction:
        time.sleep(retr_wait_time)


def home(stepper, pre_exp_time = 3.0, homing_speed = 30):

    """
    Homes the stepper to the reed switch and the linear servo to retraction.

    Parameters:
    -----------
    stepper (Autostep obj): The Autostep object, defined with respect to the correct port.
                            Do NOT make this object more than once.

    pre_exp_time (fl): The time interval in secs after executing the home function.

    homing_speed (int): The speed in degs/sec with which the stepper reaches home. 
    """

    # If servo is extended, retract:
    if stepper.get_servo_angle() != 0:
        print("Retracting linear servo...")
        stepper.set_servo_angle(0)
        # Give time to reach retraction:
        time.sleep(2.0)
    else:
        print("Linear servo already retracted.")

    # Set the home position to 0:
    print("Searching for home...")
    stepper.home_to_switch(homing_speed)
    stepper.busy_wait()
    stepper.set_position(0)

    # Wait before starting experiment:
    print(f"Home found. Position is {stepper.get_position()}.", 
          f" Experiment starting in {pre_exp_time} seconds.")
    time.sleep(pre_exp_time)


def sniff(AIN_int=0):

    """
    Get PID readings from the `AIN_int` AIN on the LabJack U3 DAQ.

    Parameters:
    -----------
    AIN_int (int): The analog input (AIN) channel the U3 reads from. 
        Will be 0 or 1. Default is 0. 
    """

    device = u3.U3()
    PID_volt = device.getAIN(AIN_int)
    device.close()

    return PID_volt


def main(stepper):
    
    # Set up arguments:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-p", "--posns", nargs="+", type=float, required=True,
        help="A list of angular positions the tethered stimulus will move to. \
            The stimulus will poke and retract at each position in the list. \
            This argument is required.")
    parser.add_argument("-e", "--ext", type=float, default=None, 
        help="The maximum linear servo extension angle. If None, will \
            inherit the value in the `calib_servo.noexiit` file. Default \
            is None.")
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
    
    args = parser.parse_args()

    posns = args.posns
    ext_angle = args.ext
    poke_speed = args.poke_speed
    ext_wait_time = args.ext_wait_time
    retr_wait_time = args.retr_wait_time

    assert(poke_speed >= 10), \
        "The poke_speed must be 10 or greater."

    if ext_angle is None:
        with open ("calib_servo.noexiit", "r") as f:
            max_ext = f.read().rstrip('\n')
        ext_angle = float(max_ext)
    
    # Home:
    home(stepper)

    # Proceed with experimental conditions once the home is set to 0:
    if stepper.get_position() == 0:
        
        # Run move function in a separate thread:
        stepper_th = threading.Thread(target=pt_to_pt_and_poke, 
                                      args=(stepper, posns, ext_angle, poke_speed, 
                                            ext_wait_time, retr_wait_time))
        stepper_th.start()
        
        # Save data for plotting and csv:
        elapsed_times = []
        cal_times = []
        stepper_posns = []
        servo_posns = []
        PID_volts = []
        t_start = datetime.datetime.now()

        # Print and save motor parameters while move function thread is alive:
        while stepper_th.is_alive() is True:

            now = datetime.datetime.now()
            # Subtracting two datetimes gives a timedelta:
            time_delta = now - t_start
            
            # Save to list:
            elapsed_times.append(time_delta.total_seconds())
            cal_times.append(now)
            stepper_posns.append(stepper.get_position())
            servo_posns.append(stepper.get_servo_angle())
            PID_volts.append(sniff())

            # Convert timedelta to elapsed seconds:
            print(f"Elapsed time (s): {time_delta.total_seconds()}     ", 
                  f"Calendar time: {now}     ", 
                  f"Stepper output (degs): {stepper.get_position()}     ", 
                  f"Servo output (degs): {stepper.get_servo_angle()}     ",
                  f"PID (V): {sniff()}")

        # Join the stepper thread back to the main:
        stepper_th.join()

        # Save outputs to a csv:
        df = pd.DataFrame({"Elapsed time (s)": elapsed_times,
                           "Calendar time": cal_times,
                           "Stepper output (degs)": stepper_posns,
                           "Servo output (degs)": servo_posns,
                           "PID (V)": PID_volts})
        df.to_csv(t_start.strftime("%m%d%Y_%H%M%S") + '_motor_commands.csv', index=False)

        stepper.print_params()
        # Save the stepper settings and servo extension angle: 
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

        # Plot and save results:
        # Motors:
        plt.subplot(2, 1, 1)
        plt.plot(elapsed_times, stepper_posns,
                 label="stepper position (degs)")
        plt.plot(elapsed_times, servo_posns,
                 label="servo position (degs)")
        plt.xlabel("time (s)")
        plt.ylabel("motor position (degs)")
        plt.legend()
        plt.grid(True)
        # PID readings:
        plt.subplot(2, 1, 2)
        plt.plot(elapsed_times, PID_volts)
        plt.xlabel("time (s)")
        plt.ylabel("PID reading (V)")
        plt.grid(True)
        plt.savefig(t_start.strftime("%m%d%Y_%H%M%S") + '_motor_commands.png')
        plt.show()


if __name__ == "__main__":

    # Set up Autostep motors:
    # change as necessary: 
    motor_port = '/dev/ttyACM0' 
    stepper = Autostep(motor_port)
    stepper.set_step_mode('STEP_FS_128') 
    stepper.set_fullstep_per_rev(200)
    stepper.set_kval_params({'accel':30, 'decel':30, 'run':30, 'hold':30})
    # deg/s and deg/s2:
    stepper.set_jog_mode_params({'speed':60, 'accel':100, 'decel':1000}) 
    stepper.set_move_mode_to_jog()
    stepper.set_gear_ratio(1)
    stepper.enable()

    main(stepper)