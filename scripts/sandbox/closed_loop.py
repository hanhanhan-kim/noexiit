#!/usr/bin/env python3

import serial
import struct
import time
import socket

import numpy as np
from scipy.spatial.transform import Rotation as R


def write_servo_and_stepper(serial_obj, mm, deg,
    read_any_lines_at_all=False, block_like_an_idiot=False):


    if not read_any_lines_at_all:
        return

    num_read_floats = 1
    while True:
        if not block_like_an_idiot:
            return

        if len(line) > 0:
            print(line)

        if line == 'ok':
            num_read_floats -= 1
            if num_read_floats == 0:
                return


def main():
    serial_obj = serial.Serial('/dev/ttyACM0', 38400) #, timeout=1)
    time.sleep(2)
    
    HOST = '127.0.0.1'  # The server's hostname or IP address
    PORT = 27654         # The port used by the server

    np.set_printoptions(precision=2)

    time_to_wait_s = None #0.5
    max_nonacked_commands = 5
    n_nonacked_commands = 0

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

        angle_deltas = []

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
                last_cnt = cnt

            angle_deltas.append(dr_lab)

            if serial_obj.in_waiting >= 3:
                line = serial_obj.readline().decode('utf-8').strip()
                if line == 'ok':
                    n_nonacked_commands -= 1
                    print('GOT AN OK')

            time_since_last_print_s = time.time() - last_time

            if ((time_to_wait_s and time_since_last_print_s > time_to_wait_s) or
                n_nonacked_commands <= max_nonacked_commands):
                last_time = time.time()

                cnts_per_sec = (cnt - last_cnt) / time_since_last_print_s
                #print('FicTrac messages per second: {:.2f}'.format(
                #    cnts_per_sec))
                last_cnt = cnt

                # ts seems to be in microseconds for whatever reason
                time_error = time.time() - (ts / 1e6)
                #print('FicTrac is behind by {:.2f} seconds'.format(time_error))

                summed_angle_deltas = np.stack(angle_deltas).sum(axis=0)
                angle_deltas = []

                curr_position = np.array([posx, posy])
                movement_during_wait = curr_position - last_position
                last_position = curr_position
                heading_deg = (360 * heading / (2 * np.pi))
                theta = heading_deg - linear_actuator_theta_deg
                # TODO TODO TODO this probably needs to be updated in the main
                # loop (not the part that only happens before sending a command)
                # as the angle_deltas are (and then sum in here, appropriately)
                linac_pos_delta = \
                    np.linalg.norm(movement_during_wait) * np.cos(theta)

                linac_pos = min(max(0, linac_pos + linac_pos_delta), 10)
                linear_actuator_theta_deg = linear_actuator_theta_deg + theta

                print(n_nonacked_commands)
                print(summed_angle_deltas)
                radian_heading_delta = summed_angle_deltas[2]
                deg_heading_delta = 360 * (radian_heading_delta / (2 * np.pi))

                #print('movement_during_wait: ({:.2f}, {:.2f})'.format(
                #    *movement_during_wait))
                '''
                print('heading_deg: {:.2f}'.format(heading_deg))
                print('theta: {:.2f}'.format(theta))
                print('linac_pos_delta: {:.2f}'.format(linac_pos_delta))
                print('linac_pos: {:.2f}'.format(linac_pos))
                print('linear_actuator_theta_deg: {:.2f}'.format(
                    linear_actuator_theta_deg))
                print('')
                '''

                serial_obj.write(struct.pack('ff',
                    linac_pos, deg_heading_delta))
                n_nonacked_commands += 1


if __name__ == '__main__':
    main()
