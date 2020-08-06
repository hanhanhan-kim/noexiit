#!/usr/bin/env python3

from __future__ import print_function

import socket
import time
import datetime
import atexit
import datetime
import argparse

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.interpolate import interp1d

from autostep import Autostep
from butter_filter import ButterFilter


def main():
    # SET UP PARAMS:
    #---------------------------------------------------------------------------------------------------------
    port = '/dev/ttyACM0'
    dev = Autostep(port)
    dev.set_step_mode('STEP_FS_64') 
    dev.set_fullstep_per_rev(200)
    dev.set_gear_ratio(1.0)
    dev.set_jog_mode_params({'speed': 200,  'accel': 1000, 'decel': 1000})
    dev.set_max_mode_params({'speed': 1000,  'accel': 30000, 'decel': 30000})
    
    # Change to jog for debugging: 
    dev.set_move_mode_to_max() 
    dev.enable()

    dev.run(0.0)  

    # Stop the stepper when script is killed:
    def stop_stepper():
        dev.run(0.0)
    atexit.register(stop_stepper)

    # Set connection parameters:
    HOST = '127.0.0.1'  # The server's hostname or IP address
    PORT = 27654         # The port used by the server

    # Set up user arguments:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("duration", type=float,
        help="Duration (s) of the closed-loop acquisition mode.")
    parser.add_argument("ball_radius", nargs="?", default=5.0, type=float,
        help="Radius of the spherical treadmill in mm. Default is 5.0 mm.")

    args = parser.parse_args()

    duration = args.duration
    ball_radius = args.ball_radius

    # Show stepper motor parameters:
    dev.print_params()
    
    # EXECUTE:
    #---------------------------------------------------------------------------------------------------------
    t_start = datetime.datetime.now()
    
    # Open the connection (FicTrac must be waiting for socket connection)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((HOST, PORT))
        
        # Initialize:
        data = ""
        elapsed_times = []
        cal_times = []
        yaw_deltas = []
        yaw_vels = []
        yaw_delta_filts = []
        yaw_vel_filts = []
        headings = []
        servo_angles = []
        stepper_posns = []

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

            # extend_delta = speed * np.cos(heading) # use heading or direction as theta? unit is mm/frame
            # # Map the range of my linear servo, 0 to 27 mm, to 0-180. Account for negatives: 
            # servo_map = interp1d([-27,27],[-180,180])
            # # Add extend_delta to current position:
            # extend_to = dev.get_servo_angle() + servo_map(extend_delta) 
            # if extend_to < 0:
            #     extend_to = 0
            # elif extend_to > 180:
            #     extend_to = 180
            # # Move!
            # gain = 1
            # stepper_pos = dev.run_with_feedback(-1 * gain * yaw_vel_filt)


            # Move!
            gain = 1 
            stepper_pos = dev.run_with_feedback(-1 * gain * yaw_vel_filt)
            
            # Get times:
            now = datetime.datetime.now()
            time_delta = now - t_start
            elapsed_time = time_delta.total_seconds()

            print(f"Elapsed time (s): {elapsed_time}")
            print(f"Calendar time: {now}")
            print(f"time delta bw frames (s): {delta_ts}")
            print(f"yaw delta (deg): {yaw_delta}")
            print(f"filtered yaw delta (deg): {yaw_delta_filt}")
            print(f"yaw velocity (deg/s): {yaw_vel}")
            print(f"filtered yaw velocity (deg/s): {yaw_vel_filt}")
            # print(f"servo extension angle (0-180): {extend_to}")
            print("\n")
    
            # Check if we are done:
            if elapsed_time >= duration:
                done = True
            
            # Save to list:
            elapsed_times.append(elapsed_time) # s
            cal_times.append(now)
            yaw_deltas.append(yaw_delta) # deg
            yaw_delta_filts.append(yaw_delta_filt) # deg
            yaw_vels.append(yaw_vel) # deg/s
            yaw_vel_filts.append(yaw_vel_filt) # deg/s
            headings.append(heading) # rad
            # servo_angles.append(extend_to)
            stepper_posns.append(stepper_pos) # deg
            stepper_posn_deltas = list(np.diff(stepper_posns)) # deg
            # Add None object to beginning of list, so its length matches with times:
            stepper_posn_deltas.insert(0, None) 

    # Stop stepper:
    dev.run(0.0)
    
    # PLOT RESULTS:
    #---------------------------------------------------------------------------------------------------------
    # Raw:
    plt.subplot(3, 1, 1)
    plt.plot(elapsed_times, yaw_deltas, '.b', label="raw")
    plt.plot(elapsed_times, yaw_delta_filts, label="filtered")
    # plt.xlabel("time (s)")
    plt.ylabel("yaw delta (deg)")
    plt.title(f"frequency cutoff = {freq_cutoff} Hz, filter order = {n}, sampling rate = {sampling_rate} Hz")
    plt.grid(True)

    # Filtered:
    plt.subplot(3, 1, 2)
    plt.plot(elapsed_times, yaw_vels, '.b', label="raw")
    plt.plot(elapsed_times, yaw_vel_filts, label="filtered")
    # plt.xlabel("time (s)")
    plt.ylabel("yaw vel (deg/s)")
    plt.title(f"frequency cutoff = {freq_cutoff} Hz, filter order = {n}, sampling rate = {sampling_rate} Hz")
    plt.grid(True)
    
    # Stepper:
    plt.subplot(3, 1, 3)
    plt.plot(elapsed_times, yaw_delta_filts, '.b', label="filtered yaw delta (deg)")
    plt.plot(elapsed_times, stepper_posn_deltas, 'r', label="stepper position delta (deg)")
    plt.xlabel("time (s)")
    plt.ylabel("yaw delta (deg)")
    plt.title(f"frequency cutoff = {freq_cutoff} Hz, filter order = {n}, sampling rate = {sampling_rate} Hz")
    plt.grid(True)
    plt.legend()

    plt.show()

    # SAVE DATA:
    #---------------------------------------------------------------------------------------------------------
    df = pd.DataFrame({"Elapsed time": elapsed_times,
                       "Calendar time": cal_times,
                       "Yaw delta (deg)": yaw_deltas,
                       "Yaw filtered delta (deg)": yaw_delta_filts,
                       "Yaw velocity (deg)": yaw_vels,
                       "Yaw filtered velocity (deg)": yaw_vel_filts,
                       "Stepper position (deg)": stepper_posns,
                       "Stepper delta (deg)": stepper_posn_deltas})
    
    df.to_csv(t_start.strftime("%m%d%Y_%H%M%S") + "_motor_loop.csv", index=False)
    

if __name__ == '__main__':
    main()