#!/usr/bin/env python3

from __future__ import print_function

import socket
import time

import numpy as np
import matplotlib.pyplot as plt

from autostep import Autostep


def get_fictrac_kins(heading, speed, delta_ts, ball_radius = 5):

    """
    Kinematic relationships between FicTrac input and motor movements. 

    Parameters:
        heading (fl): FicTrac heading. The raw value is not zero-centred. 
        speed (fl): 
        delta_ts (fl): 
        ball_radius (int): The ball radius in mm
    """
    heading_centred = heading - np.pi
    # Stepper:
    pos_set = -1 * heading_centred * ball_radius
    # Do I need a velocity set fxn, or just position?
    vel_set = np.rad2deg(heading_centred / delta_ts)
    # Linear rc servo:
    rc_set = speed * np.cos(heading_centred) 
    
    return pos_set, vel_set, rc_set


def main(dev):
    
    # # Stepper:
    # step_period = 4.0
    # step_amplitude = 45.0
    # # Servo:
    # rc_period = 8.0
    # rc_amplitude = 80.0
    # t_end = 2*step_period

    # Motor movements:
    gain = 5.0
    sleep_dt = 0.005
    t_end = 10.0 # secs

    t_start = time.time()

    # TODO change these hardcoded values to something appropriate
    # or initialize from first fictrac data
    pos_last = 0
    dev.set_position(pos_last)
    
    vel_last = 0
    dev.run(vel_last)

    t_list = []
    pos_tru_list = []
    pos_set_list = []
    
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
            # dr_lab = [float(toks[6]), float(toks[7]), float(toks[8])]
            # r_cam = [float(toks[9]), float(toks[10]), float(toks[11])]
            # r_lab = [float(toks[12]), float(toks[13]), float(toks[14])]
            # posx = float(toks[15])
            # posy = float(toks[16])
            heading = float(toks[17]) # goes from 0 to 2pi
            # step_dir = float(toks[18])
            step_mag = float(toks[19])
            # intx = float(toks[20])
            # inty = float(toks[21])
            # ts = float(toks[22])
            # seq = int(toks[23])
            delta_ts = float(toks[24])
            if delta_ts == 0:
                print("delta_ts is 0")
                continue
            # alt_ts = float(toks[25])

            # Get new setpoint values
            fictrac_kins = get_fictrac_kins(heading=heading, 
                                            speed=step_mag, 
                                            delta_ts=delta_ts)
            pos_set = fictrac_kins[0]
            vel_set = fictrac_kins[1] # needs to be in degs/sec, not 
            rc_set = fictrac_kins[2]

            # Tom: still not clear we want to use this kind of formula, as opposed
            # to basically directly passing some fictrac value.

            # Compute estimated position (since last update)
            pos_est = pos_last + delta_ts * vel_last
        
            # Caluculate position error and use to determine correction velocity
            pos_err = pos_set - pos_est
            vel_adj = vel_set + gain * pos_err
            print("vel_set: ", vel_set)
            print("pos_err: ", pos_err)

            # Set stepper to run at correction velocity and get current position
            #pos_tru = dev.run_with_feedback(vel_adj, rc_set)
            print(f'vel_adj: {vel_adj:.3f}')
            print(f'rc_set: {rc_set:.3f}')
            pos_tru = pos_est

            # Save update time and position/velocity information from update
            
            pos_last = pos_tru
            vel_last = vel_adj

            t = time.time() - t_start
            # Check if we are done
            if t >= t_end:
                done = True
            
            # Save data for plotting
            t_list.append(t)
            pos_tru_list.append(pos_tru)
            pos_set_list.append(pos_set)
        
            print('t: {:1.2f}, pos: {:1.2f}'.format(t,pos_tru))
            time.sleep(sleep_dt)

    dev.run(0.0)

    # Plot results
    plt.plot(t_list, pos_tru_list,'.b')
    plt.plot(t_list, pos_set_list, 'r')
    plt.xlabel('t (sec)')
    plt.ylabel('ang (deg)')
    plt.grid(True)
    
    plt.show()


if __name__ == '__main__':

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

    main(dev)