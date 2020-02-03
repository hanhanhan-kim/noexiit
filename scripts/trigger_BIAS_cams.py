#!/home/platyusa/.virtualenvs/behaviour/bin/python

import time
import sys
import threading
from camera_trigger import CameraTrigger

from http_BIAS_with_requests import command_BIAS_HTTP
from external_trigger import start_trigger


def main():

    # Set BIAS params:
    cam_ports = ['5010', '5020', '5030', '5040', '5050']
    config_path = '/home/platyusa/Videos/bias_test_ext_trig.json'

    # Connect cameras:
    for _, port in enumerate(cam_ports):
        command_BIAS_HTTP(
            port = port,
            cmd = "connect", 
            success_msg = "Camera on port " + f"{port}" + " connected", 
            fail_msg = "Port" + f"{port}" + " not connected"
        )
        time.sleep(1.0)

    # Load json configuration file:
    for _, port in enumerate(cam_ports):
        command_BIAS_HTTP(
            port = port,
            cmd = "load-configuration" + '=' + config_path,
            success_msg = "Loaded configuration json on port " + f"{port}",
            fail_msg = "Could not load configuration json on port " + f"{port}"
        )
        time.sleep(1.0)
    time.sleep(3.0)

    # Prompt user if they wish to continue:
    proceed = input("Continue to acquisition of frames? Enter y or n:\n")
    while True:
        if proceed == "y":
            print("Proceeding to frame acquisition . . .")
            break
        elif proceed == "n":
            print("Quitting program . . .")
            sys.exit()
        else:
            print("Please input y or n: \n")

    # Acquire frames:
    for _, port in enumerate(cam_ports):
        command_BIAS_HTTP(
            port = port,
            cmd = "start-capture",
            success_msg = "Started acquisition on port " + f"{port}",
            fail_msg = "Could not start acquisition on port " + f"{port}"
        )

    # Config json specifies an external trigger. 
    # Config json stops acquisition with a timer.

    # Execute external trigger in its own thread:
    trig_th = threading.Thread(target = start_trigger(duration=10.0))
    trig_th.start()
    trig_th.join()

if __name__ == "__main__":
    main()