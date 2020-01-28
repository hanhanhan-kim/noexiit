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