#!/usr/bin/env python

from __future__ import print_function
from autostep import Autostep
from time import perf_counter, sleep
import threading

port = '/dev/ttyACM0'

stepper = Autostep(port)
stepper.set_step_mode('STEP_FS_128') 
stepper.set_fullstep_per_rev(200)
stepper.set_jog_mode_params({'speed':200, 'accel':100, 'decel':1000})
stepper.set_move_mode_to_jog()
stepper.set_gear_ratio(1)
stepper.enable()

stepper.set_position(0.0)

        
class state(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.pos_list = [0.0, 180.0, 360.0, 2*360, 4*360, 0.0]
        self.t_now = 0
        self.params_obj = get_params(self.t_now)
        self.t_start = perf_counter()
        self.pos_now = stepper.get_position()
        self.cntr = 0
        self.pos_cmd = self.pos_list[self.cntr]
        self.stepper_obj = move_stepper(self.pos_cmd)
    def update(self):
        self.pos_now = stepper.get_position()
        self.stepper_obj = move_stepper(self.pos_cmd)
        self.stepper_obj.trigger(self.pos_cmd)
        self.cntr += 1
        self.pos_cmd = self.pos_list[self.cntr]
    def run(self):
        # while True:
        #     # self.update()
        #     self.t_now = perf_counter() - self.t_start
        #     self.params_obj = get_params(self.t_now)
        #     self.params_obj.trigger(self.t_now)
        while self.cntr <= len(self.pos_list):
            try:
                self.update()
                self.t_now = perf_counter() - self.t_start
                self.params_obj = get_params(self.t_now)
                self.params_obj.trigger(self.t_now)
            except:
                print('hooray you\'re done!')
        self.update()
        self.t_now = perf_counter() - self.t_start
        self.params_obj = get_params(self.t_now)
        self.params_obj.trigger(self.t_now)

class move_stepper:
    def __init__(self, pos_cmd):
        threading.Thread.__init__(self)
        self.pos_cmd = pos_cmd
    def reset(self):
        print('time to reset stepper')
    def trigger(self, pos_cmd):
        self.pos_cmd = pos_cmd
        stepper.move_to(self.pos_cmd)
        stepper.busy_wait()
        sleep(2.0)


class get_params:
    def __init__(self, t_now):
        threading.Thread.__init__(self)
        self.t_now = t_now
    def reset(self):
        print('time to reset params')
    def trigger(self, t_now):
        self.t_now = t_now
        print('elapsed time:{},  motor output:{}'.format(self.t_now, stepper.get_position()))


#--------------------------------------------------------------

if __name__ == '__main__':
    m = state()
    m.start()
    # pos_list = [0.0, 180.0, 360.0, 2*360, 4*360, 0.0]
    # state(pos_list).start()
    




