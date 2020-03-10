#!/usr/bin/env python3

from __future__ import print_function

import socket
import time
import atexit
import warnings

import numpy as np
import matplotlib.pyplot as plt

from autostep import Autostep


def set_motor_rotation_deg_per_s(ang_vel_deg_per_s):
    max_speed_deg_per_s = 360

    if ang_vel_deg_per_s > max_speed_deg_per_s:
        warnings.warn('max speed exceeded')
        ang_vel_deg_per_s = max_speed_deg_per_s

    elif ang_vel_deg_per_s < -max_speed_deg_per_s:
        warnings.warn('max (negative) speed exceeded')
        ang_vel_deg_per_s = -max_speed_deg_per_s

    return dev.run_with_feedback(ang_vel_deg_per_s)


def angular_diff_rad(a0_rad, a1_rad):
    periodicity = 2 * np.pi
    half_period = periodicity / 2
    
    raw_diff_rad = a1_rad - a0_rad
    if raw_diff_rad > half_period:
        diff_rad = raw_diff_rad - half_period
        assert diff_rad <= half_period
    else:
        diff_rad = raw_diff_rad
    return diff_rad


def main():
    port = '/dev/ttyACM0'
    
    dev = Autostep(port)
    dev.set_step_mode('STEP_FS_64') 
    dev.set_fullstep_per_rev(200)
    dev.set_gear_ratio(1.0)
    dev.set_jog_mode_params({'speed': 200,  'accel': 1000, 'decel': 1000})
    dev.set_max_mode_params({'speed': 1000,  'accel': 30000, 'decel': 30000})
    dev.set_move_mode_to_max()
    dev.enable()
    dev.print_params()
    dev.run(0.0)  

    HOST = '127.0.0.1'  # The server's hostname or IP address
    PORT = 27654         # The port used by the server

    t_end = 120.0 # secs
    t_start = time.time()

    # TODO change these hardcoded values to something appropriate
    # or initialize from first fictrac data; I might want to change this
    # based on the homing position as 0:
    dev.set_position(0)

    # This is also what FicTrac will report as first heading.
    last_heading = 0.0
    last_ts = None

    def stop_rotation():
        dev.run(0.0)

    atexit.register(stop_rotation)
    
    # Open the connection (FicTrac must be waiting for socket connection)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((HOST, PORT))
        
        # Initialize:
        data = ""

        # Keep receiving data until FicTrac closes:
        done = False
        while not done:
            # Receive one data frame:
            new_data = sock.recv(1024) # read at most 1024 bytes, BLOCK if no data to be read
            if not new_data:
                break
            
            # Decode received data:
            data += new_data.decode('UTF-8')
            
            # Find the first frame of data:
            endline = data.find("\n")
            line = data[:endline]       # copy first frame
            data = data[endline+1:]     # delete first frame
            
            # Tokenise: 
            toks = line.split(", ")
            
            # Fixme: sometimes we read more than one line at a time,
            # should handle that rather than just dropping extra data...
            if ((len(toks) < 24) | (toks[0] != "FT")):
                print('Bad read')
                continue
            
            # Extract FicTrac variables:
            # See https://github.com/rjdmoore/fictrac/blob/master/doc/data_header.txt
            # cnt = int(toks[1])
            # dr_cam = [float(toks[2]), float(toks[3]), float(toks[4])]
            # err = float(toks[5])
            dr_lab = [float(toks[6]), float(toks[7]), float(toks[8])]
            # r_cam = [float(toks[9]), float(toks[10]), float(toks[11])]
            # r_lab = [float(toks[12]), float(toks[13]), float(toks[14])]
            # posx = float(toks[15])
            # posy = float(toks[16])
            heading = float(toks[17]) # goes from 0 to 2pi
            # step_dir = float(toks[18])
            # step_mag = float(toks[19])
            # intx = float(toks[20])
            # inty = float(toks[21])
            ts = float(toks[22])
            # seq = int(toks[23])
            delta_ts = float(toks[24]) / 1e9
            
            if delta_ts == 0:
                if last_ts is None:
                    last_ts = ts
                    last_heading = heading

                print("delta_ts is 0")
                continue
            # alt_ts = float(toks[25])

            # Old value of computing angular velocity in rad / sec.
            '''
            ang_vel_rad_per_frame = dr_lab[2]
            ang_vel_deg_per_frame = np.rad2deg(ang_vel_rad_per_frame)
            ang_vel_deg_per_s = ang_vel_deg_per_frame / delta_ts
            '''

            # NOTE: it seems this new way is wrong, perhaps because integrated
            # heading is not what we expect.
            #'''
            # Alternative way of computing angular velocity in rad / sec.
            if last_ts is None:
                last_ts = ts
                last_heading = heading
                continue

            time_since_last_update_s = (ts - last_ts) / 1e9

            heading_delta_since_last_update_rad = angular_diff_rad(
                last_heading, heading
            )
            heading_delta_since_last_update_deg = \
                np.rad2deg(heading_delta_since_last_update_rad)

            ang_vel_deg_per_s = \
                heading_delta_since_last_update_deg / time_since_last_update_s
            
            # (end alternative way)
            #'''

            # Move stepper based on heading difference:

            print("delta_ts is ", delta_ts)
            print('old way of calculating ang_vel (deg):', np.rad2deg(dr_lab[2]) / delta_ts)
            print("time_since_last_update_s: ", time_since_last_update_s)
            print("heading_delta_since_last_update_rad:", heading_delta_since_last_update_rad)
            print("ang_vel_deg_per_s:", ang_vel_deg_per_s)
            print("\n")
            # stim_disp = step_mag * np.cos()

            # (also part of alternative way of calculating angular vel)
            last_ts = ts
            last_heading = heading

            #set_motor_rotation_deg_per_s(ang_vel_deg_per_s)

            t = time.time() - t_start
            # Check if we are done
            if t >= t_end:
                done = True
            
            # Save data for plotting
            # ang_vel.append(ang_vel)

            # print('t: {:1.2f}, pos: {:1.2f}'.format(t, ang_vel))

    # Plot results
    # plt.plot(t_list, pos_tru_list,'.b')
    # plt.plot(t_list, pos_set_list, 'r')
    # plt.xlabel('t (sec)')
    # plt.ylabel('ang (deg)')
    # plt.grid(True)
    
    # plt.show()
    

if __name__ == '__main__':
    main()