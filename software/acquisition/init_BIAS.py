#!/usr/bin/env python3

"""
Initialize Will Dickson's BIAS (Basic Image Acquisition Software) for multi-cam,
externally synchronized video recordings. Loads a .json configuration file. 
"""

import time
import json
import threading

from command_BIAS import command_BIAS
from start_trigger import start_trigger


def init_BIAS(cam_ports, config_path, backoff_time=1.0):

    """
    Initializes BIAS with HTTP commands. In BIAS, connects cameras, then loads 
    specified json configuration file, then prompts user before starting frame 
    capture. If the json specifies external triggering, frame capture will not 
    initiate acquisition. Will instead wait and listen for an external triggering 
    cue. 

    Parameters:
    -----------
    cam_ports (list): A list of strings specifying the server of each camera port. 

    config_path (str): The path to the json configuration file for BIAS.

    backoff_time (fl): The interval of time between each BIAS HTTP command.
    """

    # Connect cameras:
    for port in cam_ports:
        command_BIAS(
            port = port,
            cmd = "connect", 
            success_msg = f"Camera on port {port} connected", 
            fail_msg = f"Port {port} not connected"
        )
        time.sleep(backoff_time)

    # Load json configuration file:
    for port in cam_ports:

        # First check if the target json is already loaded:
        current_json = command_BIAS(
            port = port,
            cmd = "get-configuration",
            success_msg = f"Got config json on port {port}",
            fail_msg = f"Could not get config json on port {port}"
        ).get("value")
        
        time.sleep(backoff_time)

        with open(config_path, "r") as f:
            target_json = json.load(f)

        if current_json == target_json:
            print(f"Current json on port {port} is already the target json. Continuing ...")

        else:
            print(f"Current json on port {port} is not the target json. Loading target json ...")
            command_BIAS(
                port = port,
                cmd = f"load-configuration={config_path}",
                success_msg = f"Loaded configuration json on port {port}",
                fail_msg = f"Could not load configuration json on port {port}"
            )
            time.sleep(backoff_time)

    time.sleep(3.0)

    # Prompt user if they wish to continue:
    skip = False
    while True:
        proceed = input("Continue to acquisition of frames? Enter y or n:\n")
        if proceed == "y":
            print("Proceeding to frame acquisition . . .")
            break
        elif proceed == "n":
            print("Skipping acquisition . . .")
            skip = True
            break
        else:
            print("Please input y or n.")
            continue

    # Capture frames:
    if skip is False:
        for port in cam_ports:

            # First check if camera is already capturing:
            status_dict = command_BIAS(
                port = port,
                cmd = "get-status",
                success_msg = f"Got status on port {port}",
                fail_msg = f"Could not get status on port {port}"
            )
            time.sleep(backoff_time)

            is_capturing = status_dict.get("value").get("capturing")

            if is_capturing is True:
                print(f"Camera on port {port} is already capturing. Continuing ...")
                continue
            
            elif is_capturing is False:
                command_BIAS(
                    port = port,
                    cmd = "start-capture",
                    success_msg = f"Started acquisition on port {port}",
                    fail_msg = f"Could not start acquisition on port {port}"
                )

        # Config json specifies an external trigger. 
        # Config json stops acquisition with a timer.


def main():

    # Set BIAS params:
    cam_ports = ['5010', '5020', '5030', '5040', '5050']
    config_path = '/home/platyusa/Videos/bias_test_ext_trig.json'

    init_BIAS(cam_ports = cam_ports, 
              config_path = config_path)

    # Execute external trigger in its own thread:
    trig_th = threading.Thread(target = start_trigger(duration=10.0))
    trig_th.start()
    trig_th.join()


if __name__ == "__main__":
    main()
