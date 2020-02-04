#!/home/platyusa/.virtualenvs/behaviour/bin/python

import requests
import json
import sys
import time

def command_BIAS(port, cmd, success_msg, fail_msg, retries=10):

    """
    Uses HTTP request commands to control BIAS.

    Params:
    port (str): The port number of the target camera 
    cmd (str): The HTTP get command to use with BIAS
    success_msg (str): The message if port connection and HTTP response both succeed.
    fail_msg (str): The message if port connection and HTTP both fail.
    check_success (bool): Pass as true, to check the "success" key in the BIAS request response.
    retries (int): The number of retries if connection is 404 or request response has a False value to the success key.
    """

    url = "http://localhost:" + port + f"/?{cmd}"
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
        sys.exit()

    return ret_dict


def main():
    
    cam_ports = ['5010', '5020', '5030', '5040', '5050']
    config_path = '/home/platyusa/Videos/bias_test_ext_trig.json'

    # Connect cameras:
    for _, port in enumerate(cam_ports):
        command_BIAS(
            port = port,
            cmd = "connect", 
            success_msg = "Camera on port " + f"{port}" + " connected", 
            fail_msg = "Port" + f"{port}" + " not connected"
        )
        time.sleep(1.0)

    # Load json configuration file:
    for _, port in enumerate(cam_ports):

        # First check if the target json is already loaded:
        current_json_dict = command_BIAS(
            port = port,
            cmd = "get-status",
            success_msg = "Got status on port " + f"{port}",
            fail_msg = "Could not get status on port " + f"{port}"
        )

        with open(config_path, "r") as f:
            target_json = json.load(f)

        if current_json_dict == target_json:
            continue

        else:
            command_BIAS(
                port = port,
                cmd = "load-configuration" + '=' + config_path,
                success_msg = "Loaded configuration json on port " + f"{port}",
                fail_msg = "Could not load configuration json on port " + f"{port}"
            )
            time.sleep(1.0)

    time.sleep(3.0)

    # Capture frames:
    for _, port in enumerate(cam_ports):

        # First check if camera is already capturing:
        status_dict = command_BIAS(
            port = port,
            cmd = "get-status",
            success_msg = "Got status on port " + f"{port}",
            fail_msg = "Could not get status on port " + f"{port}"
        )

        is_capturing = status_dict.get("value").get("capturing")

        if is_capturing is True:
            continue
        
        elif is_capturing is False:
            command_BIAS(
                port = port,
                cmd = "start-capture",
                success_msg = "Started acquisition on port " + f"{port}",
                fail_msg = "Could not start acquisition on port " + f"{port}"
            )


    # Config json specifies an external trigger. 
    # Config json stops acquisition with a timer.


if __name__ == "__main__":
    main()