#!/home/platyusa/.virtualenvs/behaviour/bin/python

import time
import threading
from camera_trigger import CameraTrigger


def start_trigger(duration, port="/dev/ttyUSB0", freq=300, width=10):

    """
    Initiates ATmega328P external camera trigger, as set up by Will Dickson's camera_trigger repo.

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


def main():

    # Run the external trigger in its own thread:
    trig_th = threading.Thread(target=start_trigger(duration=10.0))
    trig_th.start()

    trig_th.join()


if __name__ == "__main__":
    main()