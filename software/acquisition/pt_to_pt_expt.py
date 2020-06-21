#!/usr/bin/env python3

from __future__ import print_function
from autostep import Autostep
import time
import datetime
import threading
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import datetime

from start_trigger import start_trigger
from init_BIAS import init_BIAS
from move import home, pt_to_pt_and_poke

def main():

    # SET UP PARAMS:
    #----------------------------------------------------------------------------------------

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

    # Set BIAS params:
    cam_ports = ['5010', '5020', '5030', '5040', '5050']
    config_path = '/home/platyusa/Videos/bias_behaviour_300hz_1000us.json'

    # Set external cam trigger params:
    trig_port = "/dev/ttyUSB0"
    duration = 120.0

    # Set motor function params:
    pos_list = [0.0, 90.0, 180.0, 360, 0.0]
    wait_time = 5.0
    with open ("calib_servo.noexiit", "r") as f:
        max_ext = f.read().rstrip('\n')
    ext_angle = float(max_ext)

    # EXECUTE:
    #----------------------------------------------------------------------------------------

    # Initialize BIAS, if desired:
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

        # Start external cam trigger in its own thread:
        trig_th = threading.Thread(target = start_trigger, 
                                   args = (duration, trig_port))
        trig_th.start()

        # Start move function in its own thread:
        stepper_th = threading.Thread(target=pt_to_pt_and_poke, 
                                      args=(stepper, pos_list, ext_angle, wait_time))
        stepper_th.start()
        
        # Save data for plotting and csv:
        elapsed_times = []
        cal_times = []
        stepper_posns = []
        servo_posns = []
        t_start = datetime.datetime.now()
        # t_start = datetime.datetime.now().strftime("%m%d%Y_%H%M%S")

        # Print motor parameters while move function thread is alive:
        while stepper_th.is_alive() is True:
            
            now = datetime.datetime.now()
            # Subtracting two datetimes gives a timedelta:
            time_delta = now - t_start
            
            # Save to list:
            elapsed_times.append(time_delta.total_seconds())
            cal_times.append(now)
            stepper_posns.append(stepper.get_position())
            servo_posns.append(stepper.get_servo_angle())

            # Convert timedelta to elapsed seconds:
            print(f"Elapsed time: {time_delta.total_seconds()}     ", 
                  f"Calendar time: {now}     ", 
                  f"Stepper output (degs): {stepper.get_position()}     ", 
                  f"Servo output (degs): {stepper.get_servo_angle()}")


        # Join the stepper thread back to the main:
        stepper_th.join()

        # Join the trigger thread back to the main:
        trig_th.join()

        # SAVE DATA:
        #----------------------------------------------------------------------------------------
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

        # Save outputs to a csv:
        df = pd.DataFrame({'Elapsed time': elapsed_times,
                           'Calendar time': cal_times,
                           'Stepper output (degs)': stepper_posns,
                           'Servo output (degs)': servo_posns})
        df.to_csv(t_start.strftime("%m%d%Y_%H%M%S") + '_motor_commands.csv', index=False)

        # Plot and save outputs:
        plt.plot(elapsed_times, stepper_posns,
                 elapsed_times, servo_posns)
        plt.savefig(t_start.strftime("%m%d%Y_%H%M%S") + '_motor_commands.png')
        plt.show()


if __name__ == "__main__":
    main()