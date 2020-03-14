#!/usr/bin/env python3

from __future__ import print_function

import socket
import time
import atexit
import warnings
import datetime

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

from autostep import Autostep
from butter_filter import ButterFilter


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

    # Set duration of closed loop mode:
    t_end = 60.0 # secs
    t_start = time.time()

    # Specify trackball size:
    ball_radius = 5 # mm

    # Stop the stepper when script is killed:
    def stop_stepper():
        dev.run(0.0)
    atexit.register(stop_stepper)
    
    # Open the connection (FicTrac must be waiting for socket connection)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((HOST, PORT))
        
        # Initialize:
        data = ""
        time_list = []

        yaw_delta_list = []
        yaw_vel_list = []
        yaw_delta_filt_list = []
        yaw_vel_filt_list = []

        heading_list = []
        speed_list = []
        servo_angle_list = []

        stepper_pos_list = []

        # Define filter;
        freq_cutoff = 5 # in Hz
        n = 2 # order of the filter
        sampling_rate = 100 # in Hz, in this case, the camera FPS
        filt = ButterFilter(freq_cutoff, n, sampling_rate)

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
            heading = float(toks[17]) # rads, goes from 0 to 2pi
            # step_dir = float(toks[18])
            speed = float(toks[19]) * ball_radius # rads per frame, goes from 0 to 2pi; scale by ball radius to get mm/frame
            # intx = float(toks[20])
            # inty = float(toks[21])
            # ts = float(toks[22])
            # seq = int(toks[23])
            delta_ts = float(toks[24]) / 1e9 # For me, FicTrac is using camera time, which is ns, not ms. Convert to s. Sanity check by 1/frame rate
            # alt_ts = float(toks[25])
            
            if delta_ts == 0:
                print("delta_ts is 0")
                continue

            # Compute yaw velocity:
            yaw_delta = np.rad2deg(dr_lab[2]) # deg
            yaw_vel = yaw_delta / delta_ts # deg/s            

            # Apply filter:
            yaw_delta_filt = filt.update(yaw_delta)
            yaw_vel_filt = yaw_delta_filt / delta_ts

            # Compute extension size of linear servo:
            # TODO: Add filters to servo inputs?
            # TODO: Add an explicit gain term for servo?
            extend_delta = speed * np.cos(heading) # use heading or direction as theta? unit is mm/frame
            servo_angle = dev.get_servo_angle()
            extend_by = servo_angle + extend_delta 

            # Move!
            gain = 1 
            stepper_pos = dev.run_with_feedback(-1 * gain * yaw_vel_filt, extend_by)

            print(f"time delta bw frames (s): {delta_ts}")
            print(f"yaw delta (deg): {yaw_delta}")
            print(f"filtered yaw delta (deg): {yaw_delta_filt}")
            print(f"yaw velocity (deg/s): {yaw_vel}")
            print(f"filtered yaw velocity (deg/s): {yaw_vel_filt}")
            print("\n")
    
            # Check if we are done:
            t = time.time() - t_start
            if t >= t_end:
                done = True
            
            # Save data for plotting
            time_list.append(t) # s

            yaw_delta_list.append(yaw_delta) # deg
            yaw_delta_filt_list.append(yaw_delta_filt) # deg
            yaw_vel_list.append(yaw_vel) # deg/s
            yaw_vel_filt_list.append(yaw_vel_filt) # deg/s

            heading_list.append(heading) # rad
            speed_list.append(speed) # mm/frame
            servo_angle.append(servo_angle_list)

            stepper_pos_list.append(stepper_pos) # deg
            stepper_pos_delta_list = list(np.diff(stepper_pos_list)) # deg
            stepper_pos_delta_list.insert(0, None) # Add None object to beginning of list, so its length matches with time_list

    # Stop stepper:
    dev.run(0.0)
    
    # Plot results:
    
    # Raw:
    plt.subplot(3, 1, 1)
    plt.plot(time_list, yaw_delta_list, '.b', label="raw")
    plt.plot(time_list, yaw_delta_filt_list, label="filtered")
    # plt.xlabel("time (s)")
    plt.ylabel("yaw delta (deg)")
    plt.title(f"frequency cutoff = {freq_cutoff} Hz, filter order = {n}, sampling rate = {sampling_rate} Hz")
    plt.grid(True)

    # Filtered:
    plt.subplot(3, 1, 2)
    plt.plot(time_list, yaw_vel_list, '.b', label="raw")
    plt.plot(time_list, yaw_vel_filt_list, label="filtered")
    # plt.xlabel("time (s)")
    plt.ylabel("yaw vel (deg/s)")
    plt.title(f"frequency cutoff = {freq_cutoff} Hz, filter order = {n}, sampling rate = {sampling_rate} Hz")
    plt.grid(True)
    
    # Stepper:
    plt.subplot(3, 1, 3)
    plt.plot(time_list, yaw_delta_filt_list, '.b', label="filtered yaw delta (deg)")
    plt.plot(time_list, stepper_pos_delta_list, 'r', label="stepper position delta (deg)")
    plt.xlabel("time (s)")
    plt.ylabel("yaw delta (deg)")
    plt.title(f"frequency cutoff = {freq_cutoff} Hz, filter order = {n}, sampling rate = {sampling_rate} Hz")
    plt.grid(True)
    plt.legend()

    plt.show()

    # Save data to csv:
    cal_time = [datetime.datetime.fromtimestamp(t).strftime('"%Y_%m_%d, %H:%M:%S"') for t in time_list]
    cal_time_filename = [datetime.datetime.fromtimestamp(t).strftime('"%Y_%m_%d_%H_%M_%S"') for t in time_list]

    df = pd.DataFrame({"Elapsed time": time_list,
                       "Calendar time": cal_time,

                       "Yaw delta (deg)": yaw_delta_list,
                       "Yaw filtered delta (deg)": yaw_delta_filt_list,
                       "Yaw velocity (deg)": yaw_vel_list,
                       "Yaw filtered velocity (deg)": yaw_vel_filt_list,

                       "Stepper position (deg)": stepper_pos_list,
                       "Stepper delta (deg)": stepper_pos_delta_list})
    
    df.to_csv(cal_time_filename[0], index=False)
    

if __name__ == '__main__':
    main()