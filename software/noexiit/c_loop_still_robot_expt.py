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
from noexiit.butter_filter import ButterFilter
from noexiit.move_and_get import home


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
        daq_counts = []
        ftrac_counts = []
        PID_volts = []
        yaw_vels = []
        yaw_vel_filts = []
        headings = []
        stepper_posns = []
        stepper_posn_deltas = []
        servo_posns = []

        errors = []
        corrected_vels = []

        # Initialize values
        stepper_posn = 0 # home() sets the position to 0 when reed switch is hit, so 0 makes sense
        last_heading = 0 
        crossings = 0
        old_error = 0
        cum_error = 0

        # Error correction gain terms for preventing drift
        # MUST be < 0 bc I do a *-1 in my loop
        # These values work well for FicTrac vAOV of 1.79
        k_p = -5
        k_d = -3
        k_i = 0
        
        # Experimental gain term for modifying the significance of the animal's turns; usually 1:
        k_stepper = 1

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
            ftrac_count = int(toks[1])
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
            if ftrac_count < 2:
                print("FicTrac count is less than 2")
                continue    

            # TODO: Add filters to servo inputs? Add an explicit gain term for servo?

            # Compute servo position from animal speed and heading, which is 0 to 2pi:
            servo_delta = speed * np.cos(heading) # mm/frame        
            servo_posn = servo_posn + servo_map(servo_delta) # degs

            # Global servo limits to prevent crashes:
            servo_max = 180
            if servo_posn < 0:
                servo_posn = 0
            elif servo_posn > servo_max:
                servo_posn = servo_max
            
            # Compute and filter yaw velocity:
            yaw_vel = np.rad2deg(dr_lab[2]) / delta_ts # deg/s    
            yaw_vel_filt = filt.update(yaw_vel) 

            # Get cummulative heading:
            heading = np.rad2deg(heading)
            diff = heading - last_heading

            if np.abs(diff) > 180: # some cutoff that defines discontinuity
                crossings -= np.sign(diff)

            last_heading = heading
            heading = heading + 360 * crossings
            
            # Correct for drift:
            proj_stepper_posn = stepper_posn + yaw_vel_filt * delta_ts # linear extrapolation from last vals
            error = heading - proj_stepper_posn
            # P control:
            corrected_vel = yaw_vel_filt + (k_p * error)
            # D control:
            corrected_vel += old_error * k_d
            # I control:
            corrected_vel += np.sum(cum_error) * k_i

            # Move with the corrected velocity!
            stepper_posn = dev.run_with_feedback(-1 * k_stepper * corrected_vel, servo_posn) 

            # Get times:
            now = datetime.datetime.now()
            elapsed_time = (now - t_start).total_seconds() # get timedelta obj

            # Get info from DAQ:
            counter_0_cmd = u3.Counter0(Reset=False)
            daq_count = device.getFeedback(counter_0_cmd)[0] # 1st count post-trigger is 1
            PID_volt = device.getAIN(0)
            
            print(f"Calendar time: {now}\n", 
                  f"Elapsed time (s): {elapsed_time}\n", 
                  f"Time delta bw frames (s): {delta_ts}\n",
                  f"DAQ count (frame): {daq_count}\n",
                  f"FicTrac count (frame): {ftrac_count}\n",
                  f"PID (V): {PID_volt}\n",
                  f"Filtered yaw velocity (deg/s): {yaw_vel_filt}\n",
                  f"Corrected yaw velocity (deg/s): {corrected_vel}\n",
                  f"Heading (deg): {heading}\n",
                  f"Stepper position (deg): {stepper_posn}\n",
                  f"Error (deg) = heading - stepper position: {error}\n",
                  f"Servo position (deg): {servo_posn}\n\n") 
            
            # Save:
            cal_times.append(now)
            elapsed_times.append(elapsed_time) # s
            daq_counts.append(daq_count)
            ftrac_counts.append(ftrac_count)
            PID_volts.append(PID_volt)
            yaw_vels.append(yaw_vel) # deg/s
            yaw_vel_filts.append(yaw_vel_filt) # deg/s
            headings.append(heading) # rad
            stepper_posns.append(stepper_posn) # deg
            corrected_vels.append(corrected_vel) # deg/s
            errors.append(error) # deg
            servo_posns.append(servo_posn) # deg

            # For D and I control:
            old_error = error
            cum_error = np.sum(errors)

            # TODO: Delete this?
            if len(np.diff(stepper_posns)) == 0:
                stepper_posn_deltas.append(None)
            else:
                stepper_posn_deltas.append(np.diff(stepper_posns)[-1]) # deg

    # Close DAQ: 
    device.close()

    # Stop stepper:
    dev.run(0.0)
    
    # PLOT RESULTS----------------------------------------------------------------------------------------------

    # 1. Closed loop feedback assessment:

    # Angular position (these should overlay):
    plt.subplot(3, 1, 1)
    plt.plot(elapsed_times, headings, "b", label="animal heading", markersize=5)
    plt.plot(elapsed_times, stepper_posns, "r", label="stepper position", markersize=5)
    plt.ylabel("angular position (deg)")
    plt.title(f"Corrected velocity added to feedback")
    plt.grid(True)
    plt.legend()

    # Error:
    plt.subplot(3, 1, 2)
    plt.title("error = animal heading - stepper position")
    plt.plot(elapsed_times, errors, "m", markersize=5)
    plt.ylabel("error (degs)")
    plt.grid(True)

    # Uncorrected vs corrected yaw velocities:
    plt.subplot(3, 1, 3)
    plt.plot(elapsed_times, yaw_vels, 'palegreen', markersize=1, label="input raw yaw velocity")
    plt.plot(elapsed_times, yaw_vel_filts, 'g', label="input filtered yaw velocity")
    plt.plot(elapsed_times, corrected_vels, 'c', label="output yaw velocity")
    plt.xlabel("time (s)")
    plt.ylabel("yaw velocity (deg/s)")
    plt.title(f"feedback correction added with $K_P = $ {k_p}, $K_I = $ {k_i}, $K_D = $ {k_d} | frequency cutoff = {freq_cutoff} Hz, filter order = {n}, sampling rate = {sampling_rate} Hz")
    plt.grid(True)
    plt.legend()

    plt.show()

    # 2. PID readings and motor commands:

    # PID:
    plt.subplot(3, 1, 1)
    plt.plot(elapsed_times, PID_volts)
    plt.ylabel("PID reading (V)")
    plt.grid(True)

    # Stepper (wrapped angular heading):
    plt.subplot(3, 1, 2)
    plt.plot(elapsed_times, [heading % 360 for heading in headings], "b", label="animal heading")
    plt.plot(elapsed_times, [stepper_posn % 360 for stepper_posn in stepper_posns], "r", label="stepper position")
    plt.ylabel("angular position (deg, wrapped)")
    plt.title(f"Corrected velocity added to feedback")
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
                       "DAQ count": daq_counts,
                       "FicTrac count": ftrac_counts,
                       "Yaw velocity (deg)": yaw_vels,
                       "Yaw filtered velocity (deg/s)": yaw_vel_filts,
                       "Heading (deg)": headings,
                       "Stepper position (deg)": stepper_posns,
                       "Yaw corrected velocity (deg/s)": corrected_vels,
                       "k_p for stepper feedback": k_p,
                       "k_i for stepper feedback": k_i,
                       "k_d for stepper feedback": k_d,
                       "Servo position (deg)": servo_posns,
                       "PID (V)": PID_volts
                       })
    
    df.to_csv("c_loop_" + t_start.strftime("%Y_%m_%d_%H_%M_%S") + ".csv", index=False)


if __name__ == '__main__':
    main()