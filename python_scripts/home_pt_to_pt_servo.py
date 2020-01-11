#!/home/platyusa/.virtualenvs/behaviour/bin/python

from __future__ import print_function
from autostep import Autostep
import time
import threading
import pandas as pd
import matplotlib.pyplot as plt

# Set up autostep motors:
motor_port = '/dev/ttyACM0' # change as necessary

stepper = Autostep(motor_port)
stepper.set_step_mode('STEP_FS_128') 
stepper.set_fullstep_per_rev(200)
stepper.set_jog_mode_params({'speed':200, 'accel':100, 'decel':1000}) # deg/s and deg/s2
stepper.set_kval_params({'accel':30, 'decel':30, 'run':30, 'hold':30})
stepper.set_move_mode_to_jog()
stepper.set_gear_ratio(1)
stepper.enable() 


def pt_to_pt_and_servo(pos_list, ext_angle, wait_time):
    '''
    Specifies stepper motor and servo motor behaviours according to a list of target positions. \n
    Arguments:
        pos_list: (list) list of target absolute positions to move to
        ext_angle: (float) the linear servo's extension 'angle' for full extension
        wait_time: (float) duration of time (s) for which to wait at each position in pos_list
    Returns nothing. 
    '''
    step_size = 2
    angle_list_fwd = list(range(0, ext_angle + step_size, step_size))
    angle_list_rev = list(angle_list_fwd[::-step_size])

    for _, pos in enumerate(pos_list):
        # Move stepper to pos:
        stepper.move_to(pos)
        stepper.busy_wait()
        # Extend linear servo:
        for _, angle in enumerate(angle_list_fwd):
            stepper.set_servo_angle(angle)
            while stepper.get_servo_angle() <= ext_angle is True:
                time.sleep(0.01)
        # Wait at extension:
        time.sleep(wait_time)
        # Retract linear servo:
        for _, angle in enumerate(angle_list_rev):
            stepper.set_servo_angle(angle)
            while stepper.get_servo_angle() >= 0 is True:
                time.sleep(wait_time)
        # Wait at retraction:
        time.sleep(wait_time)


# Arguments for above function:
pos_list = [0.0, 180.0, 360.0, 2*360, 540.0]
ext_angle = 180
wait_time = 5.0

# Set the home position to 0:
print('Searching for home...')
stepper.home_to_switch(100)
stepper.busy_wait()
stepper.set_position(0)

# Wait before starting experiment:
pre_exp_time = 3.0
print('Home found. Position is %f.' %stepper.get_position(), ' Experiment starting in %s seconds.' %pre_exp_time)
time.sleep(pre_exp_time)

# Proceed with experimental conditions once the home is set to 0:
if stepper.get_position() == 0:
    
    # Run move function in a separate thread:
    stepper_th = threading.Thread(target=pt_to_pt_and_servo, args=(pos_list, ext_angle, wait_time))
    stepper_th.start()
    
    # Save data for plotting and csv:
    elapsed_time = []
    stepper_pos = []
    servo_pos = []
    t_start = time.time()

    # Print motor parameters while move function thread is alive:
    while stepper_th.is_alive()is True:
        print('Elapsed time: %f' %(time.time()-t_start), 
              '     Stepper output (degs): %f' %stepper.get_position(), 
              '     Servo output (degs): %f' %stepper.get_servo_angle())
        
        elapsed_time.append(time.time()-t_start)
        stepper_pos.append(stepper.get_position())
        servo_pos.append(stepper.get_servo_angle())

    # Join the stepper thread back to the main:
    stepper_th.join()

    # Print the steper settings:
    stepper.print_params()

    # Save outputs to a csv:
    df = pd.DataFrame({'Elapsed time': elapsed_time, 
                       'Calendar time': [time.ctime(int()+t_start) for t in elapsed_time],
                       'Stepper output (degs)': stepper_pos,
                       'Servo output (degs)': servo_pos})
    df.to_csv('output.csv', index=False)

    # Plot outputs:
    plt.plot(elapsed_time, stepper_pos, 
             elapsed_time, servo_pos)
    plt.show()