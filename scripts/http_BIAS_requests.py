#!/home/platyusa/.virtualenvs/behaviour/bin/python

import requests
import json
import sys
import time


def command_BIAS_HTTP(cmd, success_msg, fail_msg):

    """
    cmd (str): The HTTP get command to use with BIAS
    success_msg (str): The message if port connection and HTTP response both succeed.
    fail_msg (str): The message if port connection and HTTP both fail.
    check_success (bool): Pass as true, to check the "success" key in the BIAS request response.
    """

    ret = requests.get("http://localhost:" + port + f"/?{cmd}")

    ret_dict = ret.json()[0]

    retries = 10
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


cam_ports = ['5010', '5020']
config_path = '/home/platyusa/Videos/bias_test_ext_trig.json'

# Connect cameras:
for _, port in enumerate(cam_ports):
    command_BIAS_HTTP(
        cmd = "connect", 
        success_msg = "Camera on port " + f"{port}" + " connected", 
        fail_msg = "Port" + f"{port}" + " not connected"
    )
    time.sleep(1.0)

# Load json configuration file:
for _, port in enumerate(cam_ports):
    command_BIAS_HTTP(
        cmd = "load-configuration" + '=' + config_path,
        success_msg = "Loaded configuration json on port " + f"{port}",
        fail_msg = "Could not load configuration json on port " + f"{port}"
    )
    time.sleep(1.0)
time.sleep(3.0)

# Acquire frames:
for _, port in enumerate(cam_ports):
    command_BIAS_HTTP(
        cmd = "start-capture",
        success_msg = "Started acquisition on port " + f"{port}",
        fail_msg = "Could not start acquisition on port " + f"{port}"
    )

# Config json specifies an external trigger. 
# Config json stops acquisition with a timer.


'''
commands = [
    lambda port: {
        'cmd': 'connect',
        'success_msg': "Camera on port " + f"{port}" + " connected",
        'fail_msg': "Port" + f"{port}" + " not connected"
    },
    lambda port: {
        'cmd': "load-configuration" + '=' + config_path,
        'success_msg': "Loaded configuration json on port " + f"{port}",
        'fail_msg': "Could not load configuration json on port " + f"{port}"
    },
    lambda port: {
        'cmd': "start-capture",
        'success_msg': "Started acquisition on port " + f"{port}",
        'fail_msg': "Could not start acquisition on port " + f"{port}"
    },
]
for kwargs_fn in commands:
    for _, port in enumerate(cam_ports):
        kwargs = kwargs_fn(port)
        checked_command(**kwargs)
        time.sleep(1.0)

'''

