#!/usr/bin/env python3

import serial
import struct
import time


def write_servo_and_stepper(serial_obj, mm_increm, deg_increm):
    serial_obj.write(struct.pack('ff', mm_increm, deg_increm))

def main():
    serial_obj = serial.Serial('/dev/ttyUSB0', 9600, timeout=1)
    while True:
        write_servo_and_stepper(serial_obj, 5.5, 10)
        time.sleep(1)
        write_servo_and_stepper(serial_obj, 15.5, 90)
        time.sleep(1)


if __name__ == '__main__':
    main()

