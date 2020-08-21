#!/usr/bin/env python3

"""
Move the tethered stimulus at 1) an angular velocity opposite in direction, 
but equal in magnitude, to the animal on the ball (stepper motor), and 2) 
to some distance away or towards the animal on the ball, given the tethered 
stimulus' angular position (linear servo). The idea is to mimic a stationary 
stimulus in a flat planar world. The animal turning right and away from a
stimulus in front of it, in the planar world, is equivalent to the stimulus 
turning left and retracting away from the animal, in the on-a-ball world.

This experiment demonstrates the closed-loop capabilities of NOEXIIT. 

It assumes an ATMega328P-based camera trigger. 
"""

from __future__ import print_function

import socket
import time
import datetime
import atexit
import threading
import argparse

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.interpolate import interp1d

from autostep import Autostep
from butter_filter import ButterFilter
from camera_trigger import CameraTrigger
from move_and_sniff import home, sniff


def main():
    # SET UP PARAMS:
    #---------------------------------------------------------------------------------------------------------
    motor_port = '/dev/ttyACM0'
    dev = Autostep(motor_port)
    dev.set_step_mode('STEP_FS_64') 
    dev.set_fullstep_per_rev(200)
    dev.set_gear_ratio(1.0)
    dev.set_jog_mode_params({'speed': 200,  'accel': 1000, 'decel': 1000})
    dev.set_max_mode_params({'speed': 1000,  'accel': 30000, 'decel': 30000})
    dev.set_move_mode_to_jog() 
    dev.enable()
    dev.run(0.0)

    # Stop the stepper when script is killed:
    def stop_stepper():
        dev.run(0.0)
    atexit.register(stop_stepper)

    # Set external cam trigger params:
    trig_port = "/dev/ttyUSB0"
    trig_delay = 1.0

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
    # Home the motors:
    home(dev)

    # The fictive resting stimulus experiment assumes the initial relative position of 
    # the stimulus to be in front of the tethered animal:
    print("Initialize the stimulus in front of the tethered animal...")
    dev.move_to(180)
    dev.busy_wait()
    # Change to jog for debugging: 
    dev.set_move_mode_to_max()
    
    # Start camera trigger first, and put it in its own thread:
    trig = CameraTrigger(trig_port)
    trig.set_freq(100)   # frequency (Hz)
    trig.set_width(10)
    trig.start()
    cam_timer = threading.Timer(duration + trig_delay, trig.stop)
    cam_timer.start()

    # I need to wait a bit before starting to stream info from FicTrac, or else I crash:
    time.sleep(trig_delay)

    # Start experiment
    print("Begin data acquisition...")
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
        stepper_posns = []
        servo_posns = []
        PID_volts = []

        # Map the range of my linear servo, 0 to 27 mm, to 0 to 180:
        servo_map = interp1d([-27,27],[-180,180])
        servo_posn = 0

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
            dr_lab = [float(toks[6]), float(toks[7]), float(toks[8])]
            heading = float(toks[17]) # rads, goes from 0 to 2pi
            speed = float(toks[19]) * ball_radius # rads per frame, goes from 0 to 2pi; scale by ball radius to get mm/frame
            delta_ts = float(toks[24]) / 1e9 # For me, FicTrac is using camera time, which is ns, not ms. Convert to s. Sanity check by 1/frame rate
            
            if delta_ts == 0:
                print("delta_ts is 0")
                continue

            # Compute yaw velocity:
            yaw_delta = np.rad2deg(dr_lab[2]) # deg
            yaw_vel = yaw_delta / delta_ts # deg/s            

            # Apply filter:
            yaw_delta_filt = filt.update(yaw_delta)
            yaw_vel_filt = yaw_delta_filt / delta_ts

            # TODO: Add filters to servo inputs?
            # TODO: Add an explicit gain term for servo?

            # Compute servo position from animal speed and heading:
            servo_delta = speed * np.cos(heading) # mm/frame; use heading or direction as theta?           
            servo_posn = servo_posn + servo_map(servo_delta) # degs

            if servo_posn < 0:
                servo_posn = 0
            elif servo_posn > 180:
                servo_posn = 180
                        
            # Move!
            gain = 1
            stepper_pos = dev.run_with_feedback(-1 * gain * yaw_vel_filt, servo_posn)

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
            print(f"servo position (deg): {servo_posn}")
            print(f"PID (V): {sniff()}")
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
            
            stepper_posns.append(stepper_pos) # deg
            stepper_posn_deltas = list(np.diff(stepper_posns)) # deg
            servo_posns.append(servo_posn) # deg

            PID_volts.append(sniff())
            
            # Add None object to beginning of list, so its length matches with times:
            stepper_posn_deltas.insert(0, None) 

    # Join the trigger thread back to the main:
    trig_th.join()

    # Stop stepper:
    dev.run(0.0)
    
    # PLOT RESULTS:
    #---------------------------------------------------------------------------------------------------------
    # # Raw:
    # plt.subplot(3, 1, 1)
    # plt.plot(elapsed_times, yaw_deltas, '.b', label="raw")
    # plt.plot(elapsed_times, yaw_delta_filts, label="filtered")
    # # plt.xlabel("time (s)")
    # plt.ylabel("yaw delta (deg)")
    # plt.title(f"frequency cutoff = {freq_cutoff} Hz, filter order = {n}, sampling rate = {sampling_rate} Hz")
    # plt.grid(True)

    # Filtered:
    plt.subplot(4, 1, 1)
    plt.plot(elapsed_times, yaw_vels, '.b', label="raw")
    plt.plot(elapsed_times, yaw_vel_filts, label="filtered")
    # plt.xlabel("time (s)")
    plt.ylabel("yaw vel (deg/s)")
    plt.title(f"frequency cutoff = {freq_cutoff} Hz, filter order = {n}, sampling rate = {sampling_rate} Hz")
    plt.grid(True)
    plt.legend()
    
    # Stepper:
    plt.subplot(4, 1, 2)
    plt.plot(elapsed_times, yaw_delta_filts, '.b', label="filtered yaw delta (deg)")
    plt.plot(elapsed_times, stepper_posn_deltas, 'r', label="stepper position delta (deg)")
    plt.xlabel("time (s)")
    plt.ylabel("yaw delta (deg)")
    plt.title(f"frequency cutoff = {freq_cutoff} Hz, filter order = {n}, sampling rate = {sampling_rate} Hz")
    plt.grid(True)
    plt.legend()

    # Servo:
    plt.subplot(4, 1, 3)
    plt.plot(elapsed_times, servo_posns, 'g')
    plt.xlabel("time (s)")
    plt.ylabel("servo position (deg)")
    plt.grid(True)

    # PID:
    plt.subplot(4, 1, 4)
    plt.plot(elapsed_times, PID_volts, "darkorange")
    plt.xlabel("time (s)")
    plt.ylabel("PID reading (V)")
    plt.grid(True)

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
                       "Stepper delta (deg)": stepper_posn_deltas,
                       "Servo position (deg)": servo_posns,
                       "PID (V)": PID_volts})
    
    df.to_csv(t_start.strftime("%m%d%Y_%H%M%S") + "_motor_loop.csv", index=False)
    

if __name__ == '__main__':
    main()