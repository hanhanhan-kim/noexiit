#!/home/platyusa/.virtualenvs/behaviour/bin/python

from __future__ import print_function
from autostep import Autostep
import time
import threading
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from start_trigger import start_trigger
from init_BIAS import init_BIAS
from move import pt_to_pt_and_poke, home


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
    config_path = '/home/platyusa/Videos/bias_test_ext_trig.json'

    # Set external cam trigger params:
    trig_port = "/dev/ttyUSB0"
    duration = 10.0

    # Set motor function params:
    pos_list = [0.0, 180.0, 360.0, 2*360, 540.0]
    wait_time = 2.0
    with open ("calib_servo.noexiit", "r") as f:
        max_ext = f.read().rstrip('\n')
    ext_angle = float(max_ext)

    # EXECUTE:
    #----------------------------------------------------------------------------------------

    # Home the motors:
    home()

    # Proceed with experimental conditions once the home is set to 0:
    if stepper.get_position() == 0:
        
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

        # Start external cam trigger in its own thread:
        trig_th = threading.Thread(target = start_trigger, 
                                   args = (duration, trig_port))
        trig_th.start()

        # Start move function in its own thread:
        stepper_th = threading.Thread(target = pt_to_pt_and_poke, 
                                      args = (pos_list, ext_angle, wait_time))
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

        # Join the trigger thread back to the main:
        trig_th.join()

        # SAVE DATA:
        #----------------------------------------------------------------------------------------

        t_cal_start = str(time.ctime(int(elapsed_time[0]) + t_start))

        stepper.print_params()
        # Save the stepper settings and servo extension angle: 
        with open(t_cal_start + "_motor_settings.txt", "a") as f:
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
        df = pd.DataFrame({'Elapsed time': elapsed_time, 
                        'Calendar time': [time.ctime(int() + t_start) for t in elapsed_time],
                        'Stepper output (degs)': stepper_pos,
                        'Servo output (degs)': servo_pos})
        df.to_csv(t_cal_start + '_motor_commands.csv', index=False)

        # Plot and save outputs:
        plt.plot(elapsed_time, stepper_pos, 
                elapsed_time, servo_pos)
        plt.savefig(t_cal_start + '_motor_commands.png')
        plt.show()


if __name__ == "__main__":
    main()