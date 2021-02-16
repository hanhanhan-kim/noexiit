#!/usr/bin/env python3

"""
Calibrates the linear servo's behaviour.
Sets the maximum extension angle to avoid crashes and overshoots, 
based on visual inspsection. Can rotate around the spherical 
treadmill with the servo held at the set max extension angle 
(useful when preparing for closed-loop experiments). 
"""

import time
import threading
import numpy as np
import argparse
import sys

from autostep import Autostep
from utils import ask_yes_no

def main():
    
    # Set up autostep motors:
    motor_port = '/dev/ttyACM0' # change as necessary

    stepper = Autostep(motor_port)
    stepper.set_step_mode('STEP_FS_128') 
    stepper.set_fullstep_per_rev(200)
    stepper.set_kval_params({'accel':30, 'decel':30, 'run':30, 'hold':30})
    stepper.set_jog_mode_params({'speed':15, 'accel':100, 'decel':1000}) # deg/s and deg/s2
    stepper.set_move_mode_to_jog()
    stepper.set_gear_ratio(1)
    stepper.enable() 

    parser = argparse.ArgumentParser(description=__doc__, 
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    
    # Amount of time to wait, so the servo can reach the set position:
    wait_time = 1.5

    # Set the home position to 0:
    print("Searching for home...")
    stepper.home_to_switch(30)
    stepper.busy_wait()
    stepper.set_position(0)
    stepper.set_servo_angle(0)
    time.sleep(wait_time) 

    # Wait before starting experiment:
    print(f"Home found. Position is {stepper.get_position():.5f}.")

    # Proceed with experimental conditions once the home is set to 0:
    if stepper.get_position() == 0:

        # Test stepper angle:
        while True:

            stepper_test_angle = float(input("Enter a stepper angle (degs) to test: \n"))

            if isinstance(stepper_test_angle, float):
                
                stepper.move_to(stepper_test_angle)
                stepper.busy_wait()

                proceed_stepper = ask_yes_no("Test another stepper angle?")
                if proceed_stepper:
                    continue
                else:
                    print("Ok! Moving on.")

            else:
                print("Please enter a number.")
                continue
        
        # Test servo max extension angle:
        while True:

            max_ext = float(input("Enter a desired max servo extension angle from 0 to 180: \n"))

            if max_ext >= 0 and max_ext <= 180:

                stepper.set_servo_angle(max_ext)
                time.sleep(wait_time) 

                proceed_servo = ask_yes_no("Are you happy with this max extension?")
                if proceed_servo:
                    print("Great! Good choice!") 
                else:
                    continue
                
            else:
                print("Please enter a valid servo extension angle from 0 to 180! \n")
                continue
        
        stepper.set_servo_angle(0)
        time.sleep(wait_time)
        stepper.move_to(0)
        stepper.busy_wait()

        with open("calib_servo.noexiit", "w") as f:
            print(max_ext, file=f)
        print(f"Saved the max servo angle, {max_ext}, in `calib_servo.noexiit`.")

        # Do closed loop prep test:
        proceed_c_loop_test = ask_yes_no("Test out the servo's max extension at various \
                                        angular positions? This test is useful preparation \
                                        for closed loop experiments.")
        
        if proceed_c_loop_test:

            pos_list = [0.0, 90.0, 180.0, 270.0, 360.0, 0.0]

            print(f"Visiting angular positions {str(pos_list).strip('[]')}, with the servo \
                fully extended to {max_ext} ...")

            for pos in pos_list:

                # Move stepper to pos:
                print(f"Moving to position {pos} ...")
                stepper.move_to(pos)
                stepper.busy_wait()
                print(f"Currently at position {pos}")

                # Extend linear servo, if servo is retracted less than max:
                if stepper.get_servo_angle() < max_ext:
                    stepper.set_servo_angle(max_ext)
                    time.sleep(wait_time) 

                time.sleep(wait_time)

                do_finish = ask_yes_no("Seen enough?")
                if do_finish:
                    break
        
            stepper.set_servo_angle(0)

        print("Finished calibration.")


if __name__ == "__main__":
    main()