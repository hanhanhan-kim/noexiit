#!/usr/bin/env python3

"""
Control Will Dickson's BIAS (Basic Image Acquisition Software) via external
HTTP commands. 
"""

import argparse
import json
import sys
import time

import requests


def command_BIAS(port, cmd, success_msg, fail_msg, retries=10):

    """
    Uses HTTP request commands to control BIAS.

    Paramseters:
    ------------
    port (str): The port number of the target camera 

    cmd (str): The HTTP get command to use with BIAS

    success_msg (str): The message if port connection and HTTP response 
        both succeed.
    fail_msg (str): The message if port connection and HTTP both fail.

    check_success (bool): Pass as true, to check the "success" key in the 
        BIAS request response.

    retries (int): The number of retries if connection is 404 or request 
        response has a False value to the success key.
    """

    url = f"http://localhost:{port}/?{cmd}"
    ret = requests.get(url)

    ret_dict = ret.json()[0]

    success = False
    while retries > 0:
        if ret.status_code == 200 and ret_dict.get('success'):
            print(success_msg)
            success = True
            break
        else:
            print('Status was 404:', ret.status_code == 404)
            assert ret.status_code in (200, 404), f'Status_code was {ret.status_code}'
        retries -= 1
        time.sleep(1.0)
        print('retrying...')

    if not success:
        print(fail_msg)
        while True:
            proceed = input("HTTP BIAS command failed. Continue? Enter y or n: \n")
            if proceed == "y":
                print("Continuing ...")
            elif proceed == "n":
                sys.exit()
            else:
                print("Please input y or n: \n")

    return ret_dict


def main():
    
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config_path",
        help="Absolute path to the .json configuration file. Include the \
            name of the .json file. \
            E.g. `/home/platyusa/Videos/bias_test_ext_trig.json`")
    parser.add_argument("backoff_time", nargs="?", type=float, default=1.0,
        help="Duration (s) between subsequent connection retries.")

    args = parser.parse_args()

    config_path = args.config_path
    backoff_time = args.backoff_time
    cam_ports = ['5010', '5020', '5030', '5040', '5050']

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
    while True:
        proceed = input("Continue to acquisition of frames? Enter y or n:\n")
        if proceed == "y":
            print("Proceeding to frame acquisition . . .")
            break
        elif proceed == "n":
            print("Quitting program . . .")
            sys.exit()
        else:
            print("Please input y or n.")
            continue

    # Capture frames:
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


if __name__ == "__main__":
    main()