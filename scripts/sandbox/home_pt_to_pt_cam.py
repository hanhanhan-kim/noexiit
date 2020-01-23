#!/home/chonk/.virtualenvs/behaviour/bin/python

from __future__ import print_function
from autostep import Autostep
from camera_trigger import CameraTrigger
import time
import threading
import pandas as pd

# Set up stepper motor:
stepper_port = '/dev/ttyACM1' # change as necessary

stepper = Autostep(stepper_port)
stepper.set_step_mode('STEP_FS_128') 
stepper.set_fullstep_per_rev(200)
stepper.set_jog_mode_params({'speed':200, 'accel':100, 'decel':1000}) # deg/s and deg/s2
stepper.set_move_mode_to_jog()
stepper.set_gear_ratio(1)
stepper.enable() 

# Set up camera trigger:
trig_port = '/dev/ttyACM2' # change as necessary

trig = CameraTrigger(trig_port)
trig.set_freq(500)   # Hz
trig.set_width(50)  # us


def move_pt_to_pt(pos_list, wait_time):
    '''
    Specifies stepper motor behaviour according to a list of target positions. \n
    Arguments:
        pos_list: (list) list of target absolute positions to move to
        wait_time: duration of time (s) for which to wait at each position in pos_list
    Returns nothing. 
    '''
    for _, pos in enumerate(pos_list):
        stepper.move_to(pos)
        stepper.busy_wait()
        time.sleep(wait_time)


# Set the home position to 0:
print('Searching for home...')
stepper.home_to_switch(100)
stepper.busy_wait()
stepper.set_position(0)

# Wait befor starting experiment:
pre_exp_time = 5.0
print('Home found. Position is %f.' %stepper.get_position(), ' Experiment starting in %s seconds.' %pre_exp_time)
time.sleep(pre_exp_time)

# Proceed with experimental conditions once the home is set to 0:
if stepper.get_position() == 0:

    # Start camera trigger:
    trig.start()

    # Arguments for above function:
    pos_list = [0.0, 180.0, 360.0, 2*360, 540.0]
    wait_time = 1.0
    
    # Run move function in a separate thread:
    stepper_th = threading.Thread(target=move_pt_to_pt, args=(pos_list, wait_time))
    stepper_th.start()
    
    elapsed_time = []
    stepper_pos = []
    t_start = time.time()

    # Print motor parameters while move function thread is alive:
    while stepper_th.is_alive()is True:
        print('elapsed time:{},  motor output (degs):{}'.format(time.time()-t_start, stepper.get_position()))
        
        elapsed_time.append(time.time()-t_start)
        stepper_pos.append(stepper.get_position())

    # Stop the camera trigger:
    trig.stop()
    
    # Join the stepper thread back to the main:
    stepper_th.join()

    # Save outputs to a csv
    df = pd.DataFrame({'elapsed time': elapsed_time, 
                       'calendar time': [time.ctime(int()+t_start) for t in elapsed_time],
                       'motor output (degs)': stepper.get_position()})
    df.to_csv('output.csv', index=False)
            
            