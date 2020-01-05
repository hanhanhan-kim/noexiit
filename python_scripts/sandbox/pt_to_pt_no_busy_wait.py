#!//home/chonk/.virtualenvs/behaviour/bin/python

from __future__ import print_function
from autostep import Autostep
import time
port = '/dev/ttyACM0'

stepper = Autostep(port)
stepper.set_step_mode('STEP_FS_128') 
stepper.set_fullstep_per_rev(200)
stepper.set_jog_mode_params({'speed':200, 'accel':100, 'decel':1000})
stepper.set_move_mode_to_jog()
stepper.set_gear_ratio(1)
stepper.enable()

# List of absolute positions:
pos_list = [0.0, 180.0, 360.0, 2*360, 4*360, 0.0]

# Save start time:
t_start = time.time()

for i, pos in enumerate(pos_list):
    if stepper.get_position() == pos:
        stepper.move_to(pos_list[i+1])
        print('elapsed time:{},  motor output:{}'.format(time.time()-t_start, stepper.get_position()))
    else:
        print('elapsed time:{},  motor output:{}'.format(time.time()-t_start, stepper.get_position()))