#!/home/platyusa/.virtualenvs/behaviour/bin/python

from __future__ import print_function
from builtins import input
from autostep import Autostep
import time
import threading
import numpy as np

# Set up autostep motors:
motor_port = '/dev/ttyACM0' # change as necessary

stepper = Autostep(motor_port)
stepper.set_step_mode('STEP_FS_128') 
stepper.set_fullstep_per_rev(200)
stepper.set_kval_params({'accel':30, 'decel':30, 'run':30, 'hold':30})
stepper.set_jog_mode_params({'speed':60, 'accel':100, 'decel':1000}) # deg/s and deg/s2
stepper.set_move_mode_to_jog()
stepper.set_gear_ratio(1)
stepper.enable() 


# Set the home position to 0:
print('Searching for home...')
stepper.home_to_switch(30)
stepper.busy_wait()
stepper.set_position(0)
stepper.set_servo_angle(0)

# Wait before starting experiment:
print('Home found. Position is %f.' %stepper.get_position())

# Proceed with experimental conditions once the home is set to 0:
if stepper.get_position() == 0:

    # Ask for user input on linear servo extension:
    while True:
        max_ext = float(input("Enter a desired max servo extension angle from 0 to 180: \n"))
        if max_ext >= 0 and max_ext <= 180:
            stepper.set_servo_angle(max_ext)
             # Give ample time for servo to reach inputted position:
            time.sleep(1.5)
            proceed = input("Are you happy with this max extension angle? Enter y or n: \n").lower()
            if proceed == "y":
                print("Great! Good choice!")
                break
            elif proceed == "n":
                continue
            else:
                print("Please input y or n: \n")
        else:
            print("Please enter a valid servo extension angle from 0 to 180! \n")

    # Reset servo to 0:
    stepper.set_servo_angle(0)
    time.sleep(1.5)
    
    # Move stepper pt to pt, with servo extended to user-inputted value:
    print("Moving the stepper with the servo fully extended ...")
    pos_list = [0.0, 90.0, 180.0, 270.0, 360.0, 0.0]
    wait_time = 1.5

    for _, pos in enumerate(pos_list):
        # Move stepper to pos:
        stepper.move_to(pos)
        stepper.busy_wait()
        # Extend linear servo, if servo is retracted less than max:
        if stepper.get_servo_angle() < max_ext:
            stepper.set_servo_angle(max_ext)
            # Provide ample time for servo angle to reach max extension:
            time.sleep(3.0)
        # Wait at extension:
        time.sleep(wait_time)

    stepper.set_servo_angle(0.0)
    # Print the steper settings:
    stepper.print_params()