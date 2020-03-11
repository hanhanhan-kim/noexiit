#!/usr/bin/env python3

from __future__ import print_function

import socket
import time
import atexit
import warnings

import numpy as np
import matplotlib.pyplot as plt

from scipy import signal
from scipy import interpolate
from autostep import Autostep

# FFT functions written by Kellan Moorse

# Return the smallest power of 2 greater than or equal to a number
def expceil(x, a=2):

    temp = np.log(x)/np.log(a)
    return a**np.ceil(temp)

# Take the fourier transform of the windowed input function
# Return amplitude, phase, and frequency-spacing
def fft(ft, t, pad=1, window=np.hanning):

    # Extract sample period
    if len(t) > 0:
        dt = np.diff(t[:2])[0]
        assert np.all(np.diff(t) - dt < dt/1e6)
    else:
        dt = t

    if window:
        ft = window(len(ft))*ft

    # Find power-of-two pad length and apply transform
    N = int(expceil(len(ft)*pad))
    ff = np.fft.fft(ft, N)
    ff = ff[:N//2]
    f = np.fft.fftfreq(N, dt)[:N//2]

    # Separate amplitude and phase
    amp = np.abs(ff)
    print(np.sum(amp**2))
    ph = np.angle(ff)

    return (amp, ph, f)


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

    t_end = 20.0 # secs
    t_start = time.time()

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
        heading_list = []

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
            # ts = float(toks[22])
            # seq = int(toks[23])
            delta_ts = float(toks[24]) / 1e9 # For me, FicTrac is using camera time, which is ns, not ms. Convert to s. Sanity check by 1/frame rate
            # alt_ts = float(toks[25])
            
            if delta_ts == 0:
                print("delta_ts is 0")
                continue

            # Move stepper based on heading difference:

            # Method 1:
            yaw_delta = np.rad2deg(dr_lab[2]) # deg
            yaw_vel = yaw_delta / delta_ts # deg/s

            # Filter:
            # yaw_delta_filt, _ = signal.lf(yaw_delta, delta_ts)
            # yaw_vel_filt = yaw_delta_filt / delta_ts

            # dev.run_with_feedback(yaw_vel)

            print(f"yaw delta (deg): {yaw_delta}")
            print(f"time delta bw frames (s): {delta_ts}")
            print(f"angular velocity (deg/s): {yaw_vel}")
            # print("\n")
            # print(f"yaw delta FILTERED (deg): {yaw_delta_filt}")
            # print(f"yaw velocity FILTERED (deg/s): {yaw_vel_filt}")
            print("\n")

            # Method 2:
            # Maybe don't need ...
            
            # Check if we are done:
            t = time.time() - t_start
            if t >= t_end:
                done = True
            
            # Save data for plotting
            time_list.append(t)
            yaw_delta_list.append(yaw_delta)
            yaw_vel_list.append(yaw_vel)
            heading_list.append(np.rad2deg(heading))

    # Find frequency domain with an FFT:
    f = interpolate.interp1d(time_list, yaw_delta_list)
    t_interp = np.linspace(time_list[0], time_list[-1], len(time_list))
    y_interp = f(t_interp)
    amp, _, freq = fft(np.array(y_interp), np.array(t_interp))

    # Apply Butterworth filter, given frequency vs. power plot (see below)
    b, a = signal.butter(10, 5, fs=320)
    print("SHAPES: ", a.shape, b.shape)
    y_filtered = signal.lfilter(b, a, y_interp)

    # Plot results
    # Raw:
    plt.subplot(3, 1, 1)
    plt.plot(time_list, np.array(yaw_delta_list), '.b')
    plt.plot(t_interp, y_filtered)
    plt.xlabel("time (s)")
    plt.ylabel("yaw delta (deg)")
    plt.grid(True)

    # Filtered:
    plt.subplot(3, 1, 2)
    plt.plot(freq, amp, 'r')
    plt.xlabel("frequency")
    plt.ylabel("approx power")
    plt.grid(True)

    # Filtered on log scale:
    plt.subplot(3,1,3)
    plt.semilogy(freq, amp, 'r')
    plt.xlabel("frequency")
    plt.ylabel("log approx power")
    plt.grid(True)

    plt.show()
    

if __name__ == '__main__':
    main()