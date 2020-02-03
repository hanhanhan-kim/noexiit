#!/home/platyusa/.virtualenvs/behaviour/bin/python

import time
import threading
from camera_trigger import CameraTrigger


def trig_ext_multicams(port='/dev/ttyUSB0', duration=10.0, freq=300, width=10):

    """
    port (str): The port that the ATmega328P is connected to--defaulted to '/dev/ttyUSB0'.
    duration (fl): The duration of time to run the external trigger, in seconds.
    freq (int): The frame rate of the recording.
    width (int): The pulse width of the trig's square wave. Is NOT the exposure time.
    """

    trig = CameraTrigger(port)
    trig.set_freq(freq)   # frequency (Hz)
    trig.set_width(width)  # pulse width (us); is not exposure time

    print('start')
    trig.start()

    time.sleep(duration) # match to BIAS timer

    print('stop')
    trig.stop()

trig_ext_multicams()


def main():

    # Run the external trigger in its own thread:
    trig_th = threading.Thread(target=trig_ext_multicams())
    trig_th.start()

    trig_th.join()


if __name__ == "main":
    main()

