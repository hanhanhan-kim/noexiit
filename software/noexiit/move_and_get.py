#!/usr/bin/env python3

"""
Moves the tethered stimulus to each angular position in a list 
of specified positions. Upon arriving at a position, extends the 
tethered stimulus for a fixed duration. Then retracts the tethered 
stimulus for a fixed duration.

Prints, but does not stream nor save, data.

Example command:
./move_and_get.py 10 2 2 -p 180 0 -e 90
"""

from autostep import Autostep
import time
import datetime
import threading
import argparse
import atexit
import csv
import sys

import yaml
import numpy as np
import matplotlib.pyplot as plt
import u3


def pt_to_pt_and_poke(stepper, posns, ext_angle, poke_speed, 
                      ext_wait_time, retr_wait_time):
    
    '''
    Specifies stepper motor and servo motor behaviours according to a 
    list of target positions. 
    Can be interrupted by flipping the `_moving_motors` flag to False.

    Parameters:
    -----------
        stepper (Autostep): The Autostep object, defined with the correct port. 
            E.g. Autostep("/dev/ttyACM0")
            Do NOT make this object more than once. 

        posns (list of floats): List of target absolute positions to move to.

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

    global _moving_motors
    _moving_motors = True

    for pos in posns:

        if not _moving_motors:
            print("Stopping movements ...")
            break

        # Move stepper to pos:
        stepper.move_to(pos)
        stepper.busy_wait()
        if not _moving_motors:
            print("Stopping movements ...")
            break

        # Wait at initial retraction:
        time.sleep(retr_wait_time)
        if not _moving_motors:
            print("Stopping movements ...")
            break

        # Extend linear servo:
        for angle in fwd_angles:
            stepper.set_servo_angle(angle)
            while stepper.get_servo_angle() <= ext_angle is True:
                time.sleep(dt)
        if not _moving_motors:
            print("Stopping movements ...")
            break

        # Wait at extension:
        time.sleep(ext_wait_time)
        if not _moving_motors:
            print("Stopping movements ...")
            break

        # Retract linear servo:
        for angle in rev_angles:
            stepper.set_servo_angle(angle)
            while stepper.get_servo_angle() >= 0 is True:
                time.sleep(dt)
        if not _moving_motors:
            print("Stopping movements ...")
            break

        # Wait at retraction:
        time.sleep(retr_wait_time)
        if not _moving_motors:
            print("Stopping movements ...")
            break


def home(stepper, pre_exp_time = 1.5, homing_speed = 30):

    """
    Homes the stepper to the reed switch and the linear servo to retraction.

    Parameters:
    -----------
    stepper (Autostep): The Autostep object, defined with the correct port. 
        E.g. Autostep("/dev/ttyACM0")
        Do NOT make this object more than once. 

    pre_exp_time (fl): The time interval in secs after executing the home function.

    homing_speed (int): The speed in degs/sec with which the stepper reaches home. 
    """

    # TODO: Check if set_servo_angle() and set_servo_angle_alt() are blocking;
    # Otherwise, retract both simultaneously, if neither are already homed.
    # If servos are extended, retract:
    if stepper.get_servo_angle() != 0:
        print("Retracting linear servo...")
        stepper.set_servo_angle(0)
        # Give time to reach retraction:
        time.sleep(2.0)
    else:
        print("Linear servo already retracted.")
    if stepper.get_servo_angle_alt() != 0:
        print("Retracting other linear servo...")
        stepper.set_servo_angle_alt(0)
        # Give time to reach retraction:
        time.sleep(2.0)
    else:
        print("Other linear servo already retracted.")

    # Set the home position to 0:
    print("Searching for home...")
    stepper.home_to_switch(homing_speed)
    stepper.busy_wait()
    stepper.set_position(0)

    # Wait before starting experiment:
    print(f"Home found. Position is {stepper.get_position()}. \nContinuing in {pre_exp_time} seconds ...")
    time.sleep(pre_exp_time)


def save_params(stepper, fname):

    """
    Save autostep stepper motor parameters to .txt file. 

    Parameters:
    -----------
    stepper (Autostep): The Autostep object, defined with the correct port. 
        E.g. Autostep("/dev/ttyACM0")
        Do NOT make this object more than once. 

    fname (str): Path to which to save the .txt file.
    """

    with open(fname, "a") as f:

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


def get_time_from_pt_to_pt(stepper, posns, movement_mode="jog"):

    """
    Get the time it takes to go from point to point, given the 
    movement mode (either 'jog' or 'max'). This calculation does not 
    consider the amount of time it takes for the servo to extend and 
    retract. 

    Parameters:
    -----------
    stepper (Autostep): The Autostep object, defined with the correct port. 
            E.g. Autostep("/dev/ttyACM0")
            Do NOT make this object more than once. 

    posns (list of floats): List of target absolute positions to move to.
    
    movement_mode (str): The movement mode used to control the stepper motor. 
        Either 'jog' or 'max'.

    Returns:
    --------
    The total duration of time it takes for the stepper motor to move from 
    point to point. 
    """

    if movement_mode == "jog":
        movement_params = stepper.get_jog_mode_params()
        
    elif movement_mode == "max":
        movement_params = stepper.get_max_mode_params()

    else: 
        raise ValueError("Invalid movement mode. \
            Please input either 'jog' or 'max'.")

    # Point-to-point motion model is that the motor accelerates, 
    # until it reaches the set speed. Then, it begins deceleration, 
    # such that it reaches a speed of 0 upon arriving at the destination. 
    accel = movement_params["accel"] 
    decel = movement_params["decel"] 
    speed = movement_params["speed"] 

    t_accel = speed / accel
    t_decel = speed / decel

    total_duration = 0
    for i, _ in enumerate(posns):

        # I'll error if I'm on the last index, because I need to work with 
        # the value that's one ahead, in order to take a difference. 
        if i == len(posns) - 1:
            break 
        if i == 0: 
            # When traveling to the very initial position in the list, we can 
            # assume that the motor is travelling from 0 to the very initial 
            # position. Realize that the servo motor does not extend or retract 
            # at the implicit starting position of 0. 
            ang_diff = np.abs(posns[i] - 0)
        else:
            ang_diff = np.abs(posns[i+1] - posns[i])

        t_speed = ang_diff / speed
        t_from_pt_to_pt = t_accel + t_speed + t_decel
        total_duration += t_from_pt_to_pt
    
    return total_duration


def stream_to_csv(stepper, csv_path, duration=None):
            
    """
    Saves motor commands to csv. Uses a global `_got_motors` flag so that 
    if run in a thread, the flag can be switched to end the stream.
    
    Parameters:
    -----------
    stepper (Autostep): The Autostep object, defined with the correct port. 
        E.g. Autostep("/dev/ttyACM0")
        Do NOT make this object more than once. 

    csv_path (str): Path to which to stream the .csv.
    
    duration (fl or None): If None (default), this function will stream to
        csv forever, until the `_got_motors` flag is manually switched. 
        Otherwise, takes a duration (secs) for which the data streams. 
    """

    # TODO: add overwrite handling 

    column_names = ["datetime", 
                    "stepper position (deg)", 
                    "servo_0 position (deg)", 
                    "servo_1 position (deg)"]

    if sys.version_info >= (3, 0):
        open_kwargs = dict(newline="")
    else:
        open_kwargs = dict()

    csv_file_handle = open(csv_path, "w", **open_kwargs)
    csv_writer = csv.DictWriter(csv_file_handle, fieldnames=column_names)
    csv_writer.writeheader()

    global _getting_motors
    _getting_motors = True
    
    if duration == None:

        while _getting_motors:

            now = datetime.datetime.now()
            stepper_posn = stepper.get_position()
            servo_0_posn = stepper.get_servo_angle()
            servo_1_posn = stepper.get_servo_angle_alt()

            print(f"{column_names[0]}: {now}\n", 
                  f"{column_names[1]}: {stepper_posn}\n", 
                  f"{column_names[2]}: {servo_0_posn}\n",
                  f"{column_names[3]}: {servo_1_posn}\n\n") 

            csv_writer.writerow({column_names[0]: now, 
                                column_names[1]: stepper_posn, 
                                column_names[2]: servo_0_posn,
                                column_names[3]: servo_1_posn})

            if _getting_motors == False:
                break
    
    else:

        t_start = datetime.datetime.now()
        while True:

            now = datetime.datetime.now()
            stepper_posn = stepper.get_position()
            servo_0_posn = stepper.get_servo_angle()
            servo_1_posn = stepper.get_servo_angle_alt()

            print(f"{column_names[0]}: {now}\n", 
                  f"{column_names[1]}: {stepper_posn}\n", 
                  f"{column_names[2]}: {servo_0_posn}\n",
                  f"{column_names[3]}: {servo_1_posn}\n\n") 

            csv_writer.writerow({column_names[0]: now, 
                                column_names[1]: stepper_posn, 
                                column_names[2]: servo_0_posn,
                                column_names[3]: servo_1_posn})

            if (now - t_start).total_seconds() >= duration:
                print("Stopping the motor commands stream to csv ...")
                break

    print("Closing motors' .csv handle ...")
    csv_file_handle.close()
    print("Closed motors' .csv handle.")


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
    parser = argparse.ArgumentParser(description=__doc__, 
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
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
    parser.add_argument("-e", "--ext", type=int, default=None, 
        help="The maximum linear servo extension angle. If None, will \
            inherit the value in the `config.yaml` file. Default is None.")
    
    args = parser.parse_args()

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
        AIN0_volts = []
        stepper_posns = []
        servo_posns = []
        
        # Set up DAQ:
        device = u3.U3()

        # Make motor thread:
        motors_thread = threading.Thread(target=pt_to_pt_and_poke, 
                                         args=(stepper, posns, ext_angle, poke_speed,
                                               ext_wait_time, retr_wait_time))

        # Move to first stepper position prior to data acquisition:
        print("Moving to starting stepper position.")
        stepper.move_to(posns[0])
        stepper.busy_wait()
        print("Moved to starting stepper position.")
        print("Starting experiment!")
        
        # Start motors:
        motors_thread.start()

        # Get data while motors are active::
        t_start = datetime.datetime.now()
        while motors_thread.is_alive() == True:
            
            now = datetime.datetime.now()
            elapsed_time = (now - t_start).total_seconds() # get timedelta obj

            AIN0_volt = device.getAIN(0)
            stepper_posn = stepper.get_position()
            servo_posn = stepper.get_servo_angle()

            print(f"Calendar time: {now}\n", 
                  f"Elapsed time (s): {elapsed_time}\n", 
                  f"AIN0 (V): {AIN0_volt}\n",
                  f"Stepper position (deg): {stepper_posn}\n", 
                  f"Servo position (deg): {servo_posn}\n\n") 

            # Save:
            cal_times.append(now)
            elapsed_times.append(elapsed_time)
            AIN0_volts.append(AIN0_volt)
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

        # Plot AIN0 readings:
        plt.subplot(2, 1, 2)
        plt.plot(elapsed_times, AIN0_volts)
        plt.xlabel("time (s)")
        plt.ylabel("AIN0 reading (V)")
        plt.grid(True)
        plt.show()

    # Print the motor settings: 
    stepper.print_params()
    servo_msg = f"\nlinear servo parameters \n-------------------------- \nmax extension angle: {ext_angle}\n"
    print(servo_msg)


if __name__ == "__main__":
    main()