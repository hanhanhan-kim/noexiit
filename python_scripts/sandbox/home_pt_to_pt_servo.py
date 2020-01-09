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
stepper.set_move_mode_to_jog()
stepper.set_gear_ratio(1)
stepper.enable() 


def pt_to_pt_and_servo(pos_list, ext_angle, wait_time):
    '''
    Specifies stepper motor behaviour according to a list of target positions. \n
    Arguments:
        pos_list: (list) list of target absolute positions to move to
        wait_time: duration of time (s) for which to wait at each position in pos_list
    Returns nothing. 
    '''
    for _, pos in enumerate(pos_list):
        # Move stepper to pos:
        stepper.move_to(pos)
        stepper.busy_wait()
        # Extend, wait, retract, linear servo:
        stepper.set_servo_angle(ext_angle)
        stepper.busy_wait()
        time.sleep(wait_time)
        stepper.set_servo_angle(0)
        stepper.busy_wait()


# Arguments for above function:
pos_list = [0.0, 180.0, 360.0, 2*360, 540.0]
ext_angle = 180
wait_time = 1.0

# Set the home position to 0:
print('Searching for home...')
stepper.home_to_switch(100)
stepper.busy_wait()
stepper.set_position(0)

# Wait before starting experiment:
pre_exp_time = 5.0
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

    # Plot outputs:
    plt.plot(elapsed_time, stepper_pos, 
             elapsed_time, servo_pos)

    # Save outputs to a csv:
    df = pd.DataFrame({'Elapsed time': elapsed_time, 
                       'Calendar time': [time.ctime(int()+t_start) for t in elapsed_time],
                       'Stepper output (degs)': stepper_pos,
                       'Servo output (degs)': servo_pos})
    df.to_csv('output.csv', index=False)