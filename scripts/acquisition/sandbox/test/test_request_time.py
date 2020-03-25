#!/usr/bin/env python3

import serial
import struct
import time


# TODO share w/ beetle_toucher.py by factoring this into a util module
def write_servo_and_stepper(serial_obj, mm, deg):
    serial_obj.write(struct.pack('ff', mm, deg))

    num_read_floats = 1
    while True:
        line = serial_obj.readline().decode('utf-8').strip()
        if len(line) > 0 and line != 'ok':
            print(line)

        if line == 'ok':
            num_read_floats -= 1
            if num_read_floats == 0:
                return


def main():
    serial_obj = serial.Serial('/dev/ttyUSB0', 9600)
    time.sleep(2)

    write_servo_and_stepper(serial_obj, 5.0, 0)
    time.sleep(5)
    
    n_forward = 20
    for i in range(n_forward):
        print('{}/{}'.format(i, n_forward))
        before = time.time()
        servo_pos = 0.0 if (i % 2) == 0 else 10.0
        write_servo_and_stepper(serial_obj, servo_pos, 0) #(i + 1) * 90)
        elapsed = time.time() - before
        print('{:.3f} s'.format(elapsed))
        time.sleep(1)

    '''
    n_back = 1
    for i in range(n_back):
        print('{}/{}'.format(i, n_back))
        before = time.time()
        write_servo_and_stepper(serial_obj, 10.0, (i + 1) * -90)
        elapsed = time.time() - before
        print('{:.3f} s'.format(elapsed))
        time.sleep(1)
    '''

if __name__ == '__main__':
    main()

