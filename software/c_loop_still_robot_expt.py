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

import socket
import time
import datetime
import atexit
import argparse
import threading

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.interpolate import interp1d
import u3

from camera_trigger import CameraTrigger
from autostep import Autostep
from butter_filter import ButterFilter
from move_and_sniff import home


def main():

    # SET UP PARAMATERS-----------------------------------------------------------------------------------------
    
    motor_port = '/dev/ttyACM0'
    dev = Autostep(motor_port)
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

    # Specify external cam trigger params:
    trig_port = "/dev/ttyUSB0"

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
    
    # EXECUTE---------------------------------------------------------------------------------------------------
    
    # TODO: use absolute positions to do closed loop
    home(dev)
    
    # Set up DAQ:
    device = u3.U3()

    # Map the range of my linear servo, 0 to 27 mm, to 0 to 180:
    servo_map = interp1d([-27,27],[-180,180], fill_value="extrapolate")
    servo_posn = 0

    # Define filter;
    freq_cutoff = 5 # in Hz
    n = 2 # filter order
    sampling_rate = 100 # in Hz, in this case, the camera FPS
    filt = ButterFilter(freq_cutoff, n, sampling_rate)

    # Set up cam trigger:
    trig = CameraTrigger(trig_port)
    trig.set_freq(100) # frequency (Hz)
    trig.set_width(10)
    trig.stop() # trig tends to continue running from last time

    # Initializing the camera trigger takes 2.0 secs:
    print("Starting up camera trigger (takes 2 secs) ...")
    time.sleep(2.0)

    # Make a thread to stop the cam trigger after some time:
    cam_timer = threading.Timer(duration, trig.stop)

    # Open the connection (FicTrac must be waiting for socket connection)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        
        sock.connect((HOST, PORT))
        
        data = ""
        cal_times = []
        elapsed_times = []
        counts = []
        PID_volts = []
        yaw_vels = []
        yaw_vel_filts = []
        headings = []
        stepper_posns = []
        stepper_posn_deltas = []
        servo_posns = []

        # START the DAQ counter, 1st count pre-trigger is 0:
        u3.Counter0(Reset=True)
        device.configIO(EnableCounter0=True)
        print(f"First count is pre-trigger and is 0: {device.getFeedback(u3.Counter0(Reset=False))[0]}")
        # time.sleep(2.0) # give time to see above print

        # START the trigger, and the trigger-stopping timer:
        trig.start()
        cam_timer.start()

        t_start = datetime.datetime.now()

        # Keep receiving data until cam timer ends:
        while cam_timer.is_alive():

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
            cnt = int(toks[1])
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
            
            # Prevent big speed jump on start-up bc delta_ts is weirdly small at start:
            if cnt < 2:
                print("FicTrac count is less than 2")
                continue

            # Compute and filter yaw velocity:
            yaw_vel = np.rad2deg(dr_lab[2]) / delta_ts # deg/s    
            yaw_vel_filt = filt.update(yaw_vel)     

            # TODO: Add filters to servo inputs?
            # TODO: Add an explicit gain term for servo?

            # Compute servo position from animal speed and heading:
            servo_delta = speed * np.cos(heading) # mm/frame        
            servo_posn = servo_posn + servo_map(servo_delta) # degs

            # Global servo limits to prevent crashes:
            servo_max = 180
            if servo_posn < 0:
                servo_posn = 0
            elif servo_posn > servo_max:
                servo_posn = servo_max
                        
            # Move!
            k_stepper = 1
            stepper_posn = dev.run_with_feedback(-1 * k_stepper * yaw_vel_filt, servo_posn) # TODO: try with filter off?

            # Get times:
            now = datetime.datetime.now()
            elapsed_time = (now - t_start).total_seconds() # get timedelta obj

            # Get info from DAQ:
            counter_0_cmd = u3.Counter0(Reset=False)
            count = device.getFeedback(counter_0_cmd)[0] # 1st count post-trigger is 1
            PID_volt = device.getAIN(0)
            
            print(f"Calendar time: {now}\n", 
                  f"Elapsed time (s): {elapsed_time}\n", 
                  f"Time delta bw frames (s): {delta_ts}\n",
                  f"DAQ count (frame): {count}\n",
                  f"FicTrac count (for debugging only): {count}\n",
                  f"PID (V): {PID_volt}\n",
                  f"Filtered yaw velocity (deg/s): {yaw_vel_filt}\n",
                  f"Heading (deg, wrapped): {np.rad2deg(heading) % 360}\n",
                  f"Stepper position (deg, wrapped): {stepper_posn % 360}\n", 
                  f"Servo position (deg): {servo_posn}\n\n") 
            
            # Save:
            cal_times.append(now)
            elapsed_times.append(elapsed_time) # s
            counts.append(count)
            PID_volts.append(PID_volt)
            yaw_vels.append(yaw_vel) # deg/s
            yaw_vel_filts.append(yaw_vel_filt) # deg/s
            headings.append(heading) # rad
            stepper_posns.append(stepper_posn) # deg
            servo_posns.append(servo_posn) # deg

            if len(np.diff(stepper_posns)) == 0:
                stepper_posn_deltas.append(None)
            else:
                stepper_posn_deltas.append(np.diff(stepper_posns)[-1]) # deg

    # stepper_posn_deltas = list(np.diff(stepper_posns)) # deg
    # stepper_posn_deltas.insert(0, None) # Add None object to beginning of list, so its length matches with times:

    # Close DAQ: 
    device.close()

    # Stop stepper:
    dev.run(0.0)
    
    # PLOT RESULTS----------------------------------------------------------------------------------------------
    
    # PID:
    plt.subplot(3, 1, 1)
    plt.plot(elapsed_times, PID_volts)
    plt.ylabel("PID reading (V)")
    plt.grid(True)

    # # Stepper:
    # time_diffs = list(np.diff(elapsed_times))
    # time_diffs.insert(0, None) 
    # stepper_posn_vels = [stepper_posn_delta / time_diff for stepper_posn_delta, time_diff in zip(stepper_posn_deltas, time_diffs) if stepper_posn_delta != None and time_diff != None]
    # plt.subplot(3, 1, 2)
    # plt.plot(elapsed_times, yaw_vels, label="raw yaw velocity (deg/s")
    # plt.plot(elapsed_times, yaw_vel_filts, '.b', label="filtered yaw velocity (deg/s)")
    # plt.plot(elapsed_times, stepper_posn_vels, 'r', label="stepper position velocity (deg/s)")
    # plt.ylabel("yaw delta (deg)")
    # plt.title(f"frequency cutoff = {freq_cutoff} Hz, filter order = {n}, sampling rate = {sampling_rate} Hz")
    # plt.grid(True)
    # plt.legend()

    # Angular position (these should overlay):
    wrapped_headings = [np.rad2deg(heading) % 360 for heading in headings]
    wrapped_stepper_posns = [stepper_posn % 360 for stepper_posn in stepper_posns]
    headings_minus_stepper_posns = (np.array(wrapped_stepper_posns) - np.array(wrapped_headings)) % 360
    plt.subplot(3, 1, 2)
    plt.plot(elapsed_times, wrapped_headings, ".b", label="animal heading")
    plt.plot(elapsed_times, wrapped_stepper_posns, ".r", label="stepper position")
    plt.plot(elapsed_times, headings_minus_stepper_posns, ".m", label="animal heading - stepper position") 
    plt.ylabel("angular position (deg, wrapped)")
    plt.title(f"frequency cutoff = {freq_cutoff} Hz, filter order = {n}, sampling rate = {sampling_rate} Hz")
    plt.grid(True)
    plt.legend()

    # Servo:
    plt.subplot(3, 1, 3)
    plt.plot(elapsed_times, servo_posns, 'g', label="servo position (deg)")
    plt.xlabel("time (s)")
    plt.ylabel("servo position (deg)")
    plt.title(f"servo position commands (deg)")
    plt.grid(True)
    plt.legend()

    plt.show()

    # SAVE DATA------------------------------------------------------------------------------------------
    df = pd.DataFrame({"Calendar time": cal_times,
                       "Yaw velocity (deg)": yaw_vels,
                       "Yaw filtered velocity (deg/s)": yaw_vel_filts,
                       "Stepper position (deg)": stepper_posns,
                       "Heading (deg)": [np.rad2deg(heading) for heading in headings],
                       "Servo position (deg)": servo_posns,
                       "PID (V)": PID_volts
                       })
    
    df.to_csv(t_start.strftime("%m%d%Y_%H%M%S") + "_motor_loop.csv", index=False)


if __name__ == '__main__':
    main()