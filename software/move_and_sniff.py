#!/usr/bin/env python3

"""
Move the tethered stimulus to each angular position in a list of specified 
positions, while collecting stimulus data.
Upon arriving at a position, extend the tethered stimulus. Remain extended 
for a fixed duration. Then retract the tethered stimulus. Remain retracted 
for the same fixed duration. 
Collect ongoing motor position data as well as photoionization detector data.
"""

from autostep import Autostep
import time
import datetime
import threading
import argparse
import atexit

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
        # Wait at initial retraction:
        time.sleep(retr_wait_time)
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


def main():

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
    
    # Set up arguments:
    parser = argparse.ArgumentParser(description=__doc__)
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


    # Home:
    home(stepper)

    # Proceed with experimental conditions once the home is set to 0:
    if stepper.get_position() == 0:

        cal_times = []
        elapsed_times = []
        PID_volts = []
        stepper_posns = []
        servo_posns = []
        
        # Set up DAQ:
        device = u3.U3()

        # Make motor thread:
        motors_thread = threading.Thread(target=pt_to_pt_and_poke, 
                                         args=(stepper, posns, ext_angle, poke_speed,
                                               ext_wait_time, retr_wait_time))
        
        # Start motors:
        motors_thread.start()

        # Get data while motors are active::
        t_start = datetime.datetime.now()
        while motors_thread.is_alive() == True:
            
            now = datetime.datetime.now()
            elapsed_time = (now - t_start).total_seconds() # get timedelta obj

            PID_volt = device.getAIN(0)
            stepper_posn = stepper.get_position()
            servo_posn = stepper.get_servo_angle()

            print(f"Calendar time: {now}\n", 
                  f"Elapsed time (s): {elapsed_time}\n", 
                  f"PID (V): {PID_volt}\n",
                  f"Stepper position (deg): {stepper_posn}\n", 
                  f"Servo position (deg): {servo_posn}\n\n") 

            # Save:
            cal_times.append(now)
            elapsed_times.append(elapsed_time)
            PID_volts.append(PID_volt)
            stepper_posns.append(stepper_posn)
            servo_posns.append(servo_posn)

        # Close DAQ: 
        device.close()

        # Join the motors thread back to the main:
        motors_thread.join()

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