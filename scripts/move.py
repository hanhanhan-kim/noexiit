#!/usr/bin/env python3

from __future__ import print_function
from autostep import Autostep
import time
import datetime
import threading

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def pt_to_pt_and_poke(stepper, pos_list, ext_angle, wait_time):
    
    '''
    Specifies stepper motor and servo motor behaviours according to a list of target positions. \n
    Arguments:
        stepper (Autostep obj): The Autostep object, defined with respect to the correct port.
                                Do NOT make this object more than once.
        pos_list (list): List of target absolute positions to move to.
        ext_angle (float): The linear servo's extension 'angle' for full extension.
        wait_time (float): Duration of time (s) for which to wait at each position in pos_list.
    Returns nothing. 
    '''

    angle_list_fwd = list(np.linspace(0, ext_angle, int(ext_angle)))
    angle_list_rev = list(angle_list_fwd[::-1])
    dt = 0.01

    for _, pos in enumerate(pos_list):
        # Move stepper to pos:
        stepper.move_to(pos)
        stepper.busy_wait()
        # Extend linear servo:
        for _, angle in enumerate(angle_list_fwd):
            stepper.set_servo_angle(angle)
            while stepper.get_servo_angle() <= ext_angle is True:
                time.sleep(dt)
        # Wait at extension:
        time.sleep(wait_time)
        # Retract linear servo:
        for _, angle in enumerate(angle_list_rev):
            stepper.set_servo_angle(angle)
            while stepper.get_servo_angle() >= 0 is True:
                time.sleep(dt)
        # Wait at retraction:
        time.sleep(wait_time)


def home(stepper, pre_exp_time = 3.0, homing_speed = 30):

    """
    Homes the stepper to the reed switch and the linear servo to retraction.

    Params:
    stepper (Autostep obj): The Autostep object, defined with respect to the correct port.
                            Do NOT make this object more than once.
    pre_exp_time (fl): The time interval in secs after executing the home function.
    homing_speed (int): The speed in degs/sec with which the stepper reaches home. 
    motor_port (str): The port that the Autostep Teensy connects to
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
    print("Home found. Position is %f." %stepper.get_position(), 
          " Experiment starting in %s seconds." %pre_exp_time)
    time.sleep(pre_exp_time)


def main(stepper):

    # Arguments for above function:
    pos_list = [0.0, 180.0, 360.0, 2*360, 540.0]
    wait_time = 2.0
    with open ("calib_servo.noexiit", "r") as f:
        max_ext = f.read().rstrip('\n')
    ext_angle = float(max_ext)

    # Home:
    home(stepper)

    # Proceed with experimental conditions once the home is set to 0:
    if stepper.get_position() == 0:
        
        # Run move function in a separate thread:
        stepper_th = threading.Thread(target=pt_to_pt_and_poke, 
                                      args=(stepper, pos_list, ext_angle, wait_time))
        stepper_th.start()
        
        # Save data for plotting and csv:
        elapsed_time = []
        stepper_pos = []
        servo_pos = []
        t_start = time.time()

        # Print motor parameters while move function thread is alive:
        while stepper_th.is_alive()is True:
            print("Elapsed time: %f" %(time.time()-t_start), 
                "     Stepper output (degs): %f" %stepper.get_position(), 
                "     Servo output (degs): %f" %stepper.get_servo_angle())
            
            elapsed_time.append(time.time()-t_start)
            stepper_pos.append(stepper.get_position())
            servo_pos.append(stepper.get_servo_angle())

        # Join the stepper thread back to the main:
        stepper_th.join()

        # Save results to a csv:
        cal_time = [datetime.datetime.fromtimestamp(t).strftime('"%Y_%m_%d, %H:%M:%S"') for t in elapsed_time]
        cal_time_filename = [datetime.datetime.fromtimestamp(t).strftime('"%Y_%m_%d_%H_%M_%S"') for t in elapsed_time]
        
        df = pd.DataFrame({'Elapsed time': elapsed_time, 
                        'Calendar time': cal_time,
                        'Stepper output (degs)': stepper_pos,
                        'Servo output (degs)': servo_pos})
        df.to_csv(cal_time_filename[0] + '_motor_commands.csv', index=False)

        stepper.print_params()
        # Save the stepper settings and servo extension angle: 
        with open(cal_time_filename[0] + "_motor_settings.txt", "a") as f:
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
        plt.plot(elapsed_time, stepper_pos, 
                elapsed_time, servo_pos)
        plt.savefig((cal_time_filename[0]).replace('"', '') + '_motor_commands.png')
        plt.show()


if __name__ == "__main__":

    # Set up Autostep motors:
    motor_port = '/dev/ttyACM0' # change as necessary
    stepper = Autostep(motor_port)
    stepper.set_step_mode('STEP_FS_128') 
    stepper.set_fullstep_per_rev(200)
    stepper.set_kval_params({'accel':30, 'decel':30, 'run':30, 'hold':30})
    stepper.set_jog_mode_params({'speed':60, 'accel':100, 'decel':1000}) # deg/s and deg/s2
    stepper.set_move_mode_to_jog()
    stepper.set_gear_ratio(1)
    stepper.enable()

    main(stepper)