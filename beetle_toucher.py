#!/usr/bin/env python3

import serial
import struct
import time
import socket

import numpy as np


def write_servo_and_stepper(serial_obj, mm, deg):
    serial_obj.write(struct.pack('ff', mm, deg))

    num_read_floats = 1
    while True:
        line = serial_obj.readline().decode('utf-8').strip()
        if len(line) > 0:
            print(line)

        if line == 'ok':
            num_read_floats -= 1
            if num_read_floats == 0:
                return


def main():
    serial_obj = serial.Serial('/dev/ttyUSB0', 9600) #, timeout=1)
    time.sleep(2)
    
    HOST = '127.0.0.1'  # The server's hostname or IP address
    PORT = 27654         # The port used by the server

    # Open the connection (FicTrac must be waiting for socket connection)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((HOST, PORT))
        
        data = ""

        last_time = time.time()
        last_position = None
        # Current angle of the linear actuator (should ideally be in lab coords)
        # (the stepper controls this angle)
        linear_actuator_theta_deg = 0
        # TODO fill this in w/ actual initial condition, maybe
        # changing arduino code to change initial condition as desired
        linac_pos = 0
        # SET PARAMETER:
        time_to_wait = 0.5  

        # Keep receiving data until FicTrac closes
        while True:
            # Receive one data frame
            new_data = sock.recv(1024)
            if not new_data:
                break
            
            # Decode received data
            data += new_data.decode('UTF-8')
            
            # Find the first frame of data
            endline = data.find("\n")
            line = data[:endline]       # copy first frame
            data = data[endline+1:]     # delete first frame
            
            # Tokenise
            toks = line.split(", ")
            
            # Fixme: sometimes we read more than one line at a time,
            # should handle that rather than just dropping extra data...
            if ((len(toks) < 24) | (toks[0] != "FT")):
                print('Bad read')
                continue
            
            # Extract FicTrac variables
            # (see https://github.com/rjdmoore/fictrac/blob/master/doc/data_header.txt for descriptions)
            cnt = int(toks[1])
            dr_cam = [float(toks[2]), float(toks[3]), float(toks[4])]
            err = float(toks[5])
            dr_lab = [float(toks[6]), float(toks[7]), float(toks[8])]
            r_cam = [float(toks[9]), float(toks[10]), float(toks[11])]
            r_lab = [float(toks[12]), float(toks[13]), float(toks[14])]
            posx = float(toks[15])
            posy = float(toks[16])
            heading = float(toks[17])
            step_dir = float(toks[18])
            step_mag = float(toks[19])
            intx = float(toks[20])
            inty = float(toks[21])
            ts = float(toks[22])
            seq = int(toks[23])

            if last_position is None:
               last_position = np.array([posx, posy])

            if time.time() - last_time > time_to_wait:
                last_time = time.time()
                curr_position = np.array([posx, posy])
                movement_during_wait = curr_position - last_position
                last_position = curr_position
                theta = (360 * heading / (2 * np.pi)) - linear_actuator_theta_deg
                linac_pos_delta = np.linalg.norm(movement_during_wait) * np.cos(theta)

                linac_pos = min(max(0, linac_pos + linac_pos_delta), 10)
                linear_actuator_theta_deg = linear_actuator_theta_deg + theta

                print('movement_during_wait: ({:.2f}, {:.2f})'.format(
                    *movement_during_wait))
                print('heading: {:.2f}'.format(heading))
                print('theta: {:.2f}'.format(theta))
                print('linac_pos_delta: {:.2f}'.format(linac_pos_delta))
                print('linac_pos: {:.2f}'.format(linac_pos))
                print('linear_actuator_theta_deg: {:.2f}'.format(
                    linear_actuator_theta_deg))
                print('')

                #write_servo_and_stepper(serial_obj, linac_pos, linear_actuator_theta_deg)


if __name__ == '__main__':
    main()

