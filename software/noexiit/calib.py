import time
import numpy as np
import argparse
from pathlib import Path
from os.path import expanduser

import yaml
from autostep import Autostep
from noexiit.utils import ask_yes_no

def main(config):
    
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
    
    # Amount of time to wait, so the servo can reach the set position:
    wait_time = 1.5

    # Ask user where to save data files:
    do_output_dir = ask_yes_no("Do you want to save the output data files "
                               "to a new specific directory?")
    if do_output_dir:
        
        while True:
            try:
                output_dir = expanduser(input("Specify the directory you want to save to:"))

                if not output_dir.endswith("/"):
                    output_dir = output_dir + "/"

                # Write new config.yaml if it doesn't exist:
                if Path(output_dir).is_dir() and not Path("config.yaml").is_file():
                    with open("config.yaml", "w") as f:
                        yaml.dump({"calib":{"output_dir": (output_dir)}}, f)
                    break
                
                # Read and modify existing config.yaml if it exists: 
                elif Path(output_dir).is_dir() and Path("config.yaml").is_file():
                    with open ("config.yaml") as f:
                        config = yaml.load(f, Loader=yaml.FullLoader)
                        config["calibrate"]["output_dir"] = output_dir 
                    with open("config.yaml", "w") as f:
                        yaml.dump(config, f)
                    break

                else:
                    print(f"`{output_dir}` does not exist. "
                        "Please enter a valid directory.")
                    continue

            except TypeError:
                print("Expected str, bytes or os.PathLike object, not int.")
                continue

    else:
        print("A specific output directory does not exist.")
        output_dir = str(Path.cwd()) + "/"

        # Write new config.yaml if it doesn't exist, with pwd as output path:
        if not Path("config.yaml").is_file():
            with open("config.yaml", "w") as f: 
                yaml.dump({"calib":{"output_dir": str(output_dir)}}, f)
        # Otherwise, just keep whatever's already in the .yaml file

        # If config.yaml does exist, make a new key with the pwd as the value:
        else:
            with open ("config.yaml") as f:
                config = yaml.load(f, Loader=yaml.FullLoader)
                config["calibrate"]["output_dir"] = output_dir
            with open("config.yaml", "w") as f:
                yaml.dump(config, f)


    # Set the home position to 0:
    print("Searching for home...")
    stepper.home_to_switch(30)
    stepper.busy_wait()
    stepper.set_position(0)

    # Wait before starting experiment:
    print(f"Home found. Position is {stepper.get_position():.5f}.")

    # Retract servo:
    stepper.set_servo_angle(0)
    time.sleep(wait_time) 

    # Proceed with experimental conditions once the home is set to 0:
    if stepper.get_position() == 0:

        # Test stepper angle:
        while True:

            stepper_test_angle = input("Enter a stepper angle (degs) to test: \n")

            try:
                stepper_test_angle = float(stepper_test_angle)
                
                stepper.move_to(stepper_test_angle)
                stepper.busy_wait()

                proceed_stepper = ask_yes_no("Test another stepper angle?", default="no")
                if proceed_stepper:
                    continue
                else:
                    print("Ok! Moving on.")
                    break

            except ValueError:
                print("Please enter a number.")
                continue
        
        # Test servo max extension angle:
        while True:

            max_ext = input("Enter a desired max servo extension angle from 0 to 180: \n")

            try:
                max_ext = float(max_ext)

                if max_ext >= 0 and max_ext <= 180:

                    stepper.set_servo_angle(max_ext)
                    time.sleep(wait_time) 

                    proceed_servo = ask_yes_no("Are you happy with this max extension?")
                    if proceed_servo:
                        print("Great! Good choice!") 
                        break
                    else:
                        continue
                else:
                    raise ValueError("Input angle is out of bounds.")
                
            except ValueError:
                print("Please enter a valid servo extension angle from 0 to 180! \n")
                continue
        
        print("Homing ...")
        stepper.set_servo_angle(0)
        time.sleep(wait_time)
        stepper.move_to(0)
        stepper.busy_wait()
        print("Homed")

        with open("config.yaml") as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
            config["calibrate"]["max_ext"] = max_ext
        with open("config.yaml", "w") as f:
            yaml.dump(config, f)
        print(f"Saved the max servo angle, {max_ext}, in `config.yaml`.")

        # Do closed loop prep test:
        proceed_c_loop_test = ask_yes_no("Test out the servo's max extension at various "
                                        "angular positions? \nThis test is useful preparation " 
                                        "for closed loop experiments.", default="no")
        
        if proceed_c_loop_test:

            pos_list = [0.0, 90.0, 180.0, 270.0, 360.0, 0.0]

            print(f"Visiting angular positions {str(pos_list).strip('[]')}, " 
                f"with the servo fully extended to {max_ext} ...")

            for pos in pos_list:

                # Move stepper to pos:
                print(f"Moving to position {pos} ...")
                stepper.move_to(pos)
                stepper.busy_wait()
                print(f"At position {pos}")

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