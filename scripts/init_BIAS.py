#!/home/platyusa/.virtualenvs/behaviour/bin/python

import time
import sys
import threading

from command_BIAS_HTTP import command_BIAS_HTTP
from start_trigger import start_trigger


def init_BIAS(cam_ports, config_path, duration, backoff_time=1.0):

    """
    Initializes BIAS with HTTP commands. In BIAS, connects cameras, then loads specified 
    json configuration file, then prompts user before starting frame capture.
    If the json specifies external triggering, frame capture will not initiate acquisition.
    Will instead wait and listen for an external triggering cue. 

    Parameters:

    cam_ports (list): A list of strings specifying the server of each camera port. 
    config_path (str): The path to the json configuration file for BIAS.
    duration (fl): The duration of the recording.
    backoff_time (fl): The interval of time between each BIAS HTTP command.
    """

    # Connect cameras:
    for _, port in enumerate(cam_ports):
        command_BIAS_HTTP(
            port = port,
            cmd = "connect", 
            success_msg = "Camera on port " + f"{port}" + " connected", 
            fail_msg = "Port" + f"{port}" + " not connected"
        )
        time.sleep(backoff_time)

    # Load json configuration file:
    for _, port in enumerate(cam_ports):
        command_BIAS_HTTP(
            port = port,
            cmd = "load-configuration" + '=' + config_path,
            success_msg = "Loaded configuration json on port " + f"{port}",
            fail_msg = "Could not load configuration json on port " + f"{port}"
        )
        time.sleep(backoff_time)
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
    trig_th = threading.Thread(target = start_trigger(duration=duration))
    trig_th.start()
    trig_th.join()


def main():

    # Set BIAS params:
    cam_ports = ['5010', '5020', '5030', '5040', '5050']
    config_path = '/home/platyusa/Videos/bias_test_ext_trig.json'

    init_BIAS(cam_ports = cam_ports, 
              config_path = config_path,
              duration = 10.0)


if __name__ == "__main__":
    main()