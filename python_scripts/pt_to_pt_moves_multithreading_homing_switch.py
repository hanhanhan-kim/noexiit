#!/home/chonk/.virtualenvs/behaviour/bin/python

from __future__ import print_function
from autostep import Autostep
import time
import threading

port = '/dev/ttyACM0'

stepper = Autostep(port)
stepper.set_step_mode('STEP_FS_128') 
stepper.set_fullstep_per_rev(200)
stepper.set_jog_mode_params({'speed':200, 'accel':100, 'decel':1000})
stepper.set_move_mode_to_jog()
stepper.set_gear_ratio(1)
stepper.enable() 


def move_pt_to_pt(pos_list, wait_time):
    '''
    Specifies stepper motor behaviour according to a list of target positions. 
    Arguments:
        pos_list: (list) list of target absolute positions to move to
        wait_time: duration of time (s) for which to wait at each position in pos_list
    Returns nothing. 
    '''
    for _, pos in enumerate(pos_list):
        stepper.move_to(pos)
        stepper.busy_wait()
        time.sleep(wait_time)


# Set the home position as 0:
print('Searching for home...')
stepper.home_to_switch(100)
stepper.busy_wait()
stepper.set_position(0)
print('Home found. Position is %f. Experiment starting in 5 seconds.' %stepper.get_position())
time.sleep(5.0)

# Proceed with experimental conditions once the home is set to 0. 
if stepper.get_position() == 0:

    # Arguments for above function:
    pos_list = [0.0, 180.0, 360.0, 2*360, 180.0]
    wait_time = 1.0
    
    # Run move function in a separate thread:
    stepper_th = threading.Thread(target=move_pt_to_pt, args=(pos_list, wait_time))
    stepper_th.start()

    # Print motor parameters while move function thread is alive:
    t_start = time.time()
    while stepper_th.is_alive()is True:
        print('elapsed time:{},  motor output (degs):{}'.format(time.time()-t_start, stepper.get_position()))

    # Wait until stepper thread is finished:
    stepper_th.join()