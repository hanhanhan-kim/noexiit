#!/usr/bin/env python3

"""
Demos simultaneous analog streaming and counting on the U3-HV. 
Streams analog inputs into the AIN0 pin, and counts digital 
inputs into the FIO4 pin (Counter0).

Does not initiate an external trigger, although it can support it.
See `count_frames_and_stream.py` for an example. 

Modified from Tom O'Connell's LabJack code:
https://github.com/ejhonglab/labjack/blob/main/src/labjack/labjack.py

Example command:
./stream.py stream.csv none absolute
"""

from __future__ import print_function, division

import sys
import time
import os
import traceback
from datetime import datetime, timedelta
import warnings
import atexit
import signal
import math
import csv
import argparse

import numpy as np
from LabJackPython import Device
import u3
from camera_trigger import CameraTrigger


# From table 3.2-1 with resolutions and cognate max stream scan frequencies.
# Maximum scan frequencies are in samples/s (shared across all channels).
# https://labjack.com/support/datasheets/u3/operation/stream-mode
resolution_index2max_scan_freq = {
    0: 2500,
    1: 10000,
    2: 20000,
    3: 50000
}
# TODO also provide fn to output resolution / noise (in units of volts, after
# reading Range from some device details via API). noise in table in in units of
# "Counts".

# See: https://labjack.com/support/datasheets/u3/operation/stream-mode/digital-inputs-timers-counters
# If streaming digital inputs, timers, and counters on the U3:
special_channels = {193: "AIN193", # EIO_FIO
                    194: "AIN194", # CIO 
                    200: "AIN200", # Timer0 
                    201: "AIN201", # Timer1
                    210: "AIN210", # Counter0
                    211: "AIN211", # Counter1
                    224: "AIN224", # TC_Capture
                    230: "AIN230", # Timer0 with reset
                    231: "AIN231", # Timer1 with reset
                    240: "AIN240", # Counter0 with reset
                    241: "AIN241"} # Counter1 with reset


def get_channel_name(device, channel_index):

    """
    Parameters:
    -----------
    device (subclass of `LabJackPython.Device`, like `u3.U3`): used to determine
        name and hardwareVersion of device, via `device.deviceName` and
        `device.hardwareVersion`.

    channel_index (int): index of (input) channel to get a name for.

    Returns:
    --------
    Name of channel (str), as printed on device case, unless the channel index
    is 193 or greater, in which case the key in `r` (dict) is returned. 
    """

    if not issubclass(type(device), Device):
        raise ValueError("device must be a subclass of LabJackPython.Device")

    if type(channel_index) is not int:
        raise ValueError("channel_index must be an int")

    if channel_index < 0:
        raise ValueError("channel_index must be positive")

    device_name = device.deviceName
    if device_name != "U3-HV":
        raise NotImplementedError('only U3-HV currently supported')

    if device.hardwareVersion != '1.30':
        warnings.warn("get_channel_name only tested for U3-HV with \
                      hardwareVersion=='1.30'. Labels on board may be wrong.")    

    if channel_index <= 3:
        return f"AIN{channel_index}"
    elif channel_index <= 7:
        return f"FIO{channel_index}"
    elif channel_index in special_channels.keys():
        return special_channels[channel_index]
    else:
        raise ValueError(f"channel index of {channel_index} is not a valid input on device {device_name}.")

    # TODO also support at least the other U3 variants ('U3-LV' at least, maybe
    # also whatever 'U3B' is (see setting of deviceName in u3.py)


def stream_to_csv(csv_path, duration_s=None, input_channels=None,
    resolution_index=0, input_channel_names=None, times="elapsed",
    external_trigger=None, do_overwrite=False, is_verbose=False):

    # TODO implement callbacks that can be passed into this fn, then pass stuff to
    # publish data from ROS wrapper of this script? or should i just relax the
    # separation of ROS stuff from this file?
    # TODO TODO emulate some kind of triggered acquisition functionality by starting
    # a counter on the trigger pin, and then just only start appending to CSV once
    # the count is >0 (and also start counting towards duration_s from that point)
    # (would need a pin on my stimulus control arduino to go high at the start of
    # the stimulus program though...)
    # TODO : Don't run more than one counter and/or timer. The required multiple 224 
    # channels means I have to make some fixes.
    # See: https://labjack.com/support/datasheets/u3/operation/stream-mode/digital-inputs-timers-counters

    """
    Streams AIN data. Can stream directly to a CSV.
    
    If using a counter or timer with the stream, use the 224 channel, 
    as described in the docs:
    https://labjack.com/support/datasheets/u3/operation/stream-mode/digital-inputs-timers-counters

    Channel 224 stores the most significant digit. LabJack recommends streaming the counters
    and timers in 16-bit mode (default). In other words, when using e.g. 1 counter, the counts 
    will be stored up to (2**16)-1, and will then roll over (return to 0). The number of roll overs 
    are stored in Channel 224. So to get back the total number of counts in this example, do:
    DAQ_count + TC_capture * (2**16-1). 

    Parameters:
    ------------
    csv_path (str): path of CSV to stream data to.

    duration_s (None or float): If `float`, will stop streaming to CSV after
        recording for at least this amount of time (may include slightly more
        samples from last request, as there are currently a fixed number of
        samples returned per request). If `None` (the default), will stream to
        CSV until this process exits.

    input_channels (None or list): A list of `int` channel indexes to acquire
        data from. By default, will be set to [0], which records from just AIN0
        (on a U3-HV).

    resolution_index (int): 0-3, with 0 being the highest resolution, but also
        having the slowest sampling rate. Defaults to 0.

    input_channel_names (dict or None): If passed, must be a dict with a key for
        each `int` in `input_channels`. Maps each channel index to an arbitrary
        `str` name for this channel, which will be used as the name for the
        corresponding column in the CSV. If not passed, the labels of the
        channels on the LabJack hardware will be used.

    times (str): Accepts either "elapsed" (default) or "absolute". If "elapsed", 
        a column, "time (s)", will be added to the .csv with time in seconds from 
        beginning of streaming. If "absolute", a column, "datetime" will be added 
        to the .csv with time as a string from a datetime object. N.B. Understand 
        that the offset between streaming start /s top and when those calls are 
        made are hard to predict or measure, and so using elapsed times is often 
        recommended. 

    external_trigger (dict or None): If passed, must be a dictionary with the following
        key-value pairs: 
        "port" : holds a string that specifies the path of an ATMega328P trigger port, 
            e.g. "/dev/ttyUSB0". 
        "freq" : holds an integer that specifies the trigger frequency in Hz (frame rate).
        "width" : holds an integer that specifies the pulse width in us.
        Passing the dictionary starts the ATMega328P trigger with the specified frequency
            and width.

    do_overwrite (bool): If `False` (default), will raise `IOError` if `csv_path`
        already exists. Otherwise, will overwrite the file.

    is_verbose (bool): If `True`, will print more output. Defaults to `False`.
    """

    if external_trigger is not None:

        # Set up trigger:
        trig = CameraTrigger(external_trigger["port"])
        trig.set_freq(external_trigger["freq"]) # frequency (Hz)
        trig.set_width(external_trigger["width"]) # (us)
        trig.stop()

        # Initializing the CameraTrigger takes 2.0 secs:
        print("Initializing the external trigger ...")
        time.sleep(2.0)
        print("Initialized external trigger.")

        # Kill the external trigger when the script exits (either normally or by ctrl_c):
        def stop_trigger():
            print("Stopping external trigger ...")
            trig.stop()
            print("Successfully stopped external trigger.\n")
        atexit.register(stop_trigger)

    if input_channels is None:
        input_channels = [0]

    # TODO print string label of each of above channels on particular hardware.
    # maybe assert hardware is HV version, if accessible via API.

    if duration_s is not None:
        if duration_s <= 0:
            raise ValueError("duration_s must be positive or None")

    max_scan_freq = resolution_index2max_scan_freq[resolution_index]

    # TODO ok if this isn't divided cleanly by # of channels?
    # (e.g. if # channels == 3). see alternative set of options for
    # <d>.streamConfig (SamplesPerPacket, InternalStreamClockFrequency,
    # DivideClockBy256, ScanInterval)
    # ScanFrequency "sample rate (Hz) = ScanFrequency * NumChannels"

    scan_frequency = max_scan_freq / len(input_channels)

    d = u3.U3()
    atexit.register(d.close)

    # Learn if the U3 is an HV:
    d.configU3()

    d.getCalibrationData()

    # Both configU3() and configIO() can set specific FIO pins as analog. 
    # configU3(), however, sets the power-up defaults of the U3. In contrast, 
    # configIO() sets the U3's behaviour for only this session. 
    # Both configU3() and configIO() specifies particular FIO pins as analog, 
    # via the FIOAnalog argument. FIOAnalog is an integer, such that 
    # FIOAnalog = sum(2**pin_number) for pin_number in pin_numbers. 
    # By default, FIOAnalog = 15, because on the HV, AIN0-AIN3 are fixed analog
    # channels dedicated to high-voltage (-10 to 10 V) inputs. In contrast, 
    # FIO pins can be either analog or digital, and if analog, has a 0-2.4 V range.
    FIO_channels = [2**input_channel for input_channel in input_channels 
                    if 3 < input_channel <= 7]
    FIO_int_rep = np.sum(FIO_channels)
    d.configIO(FIOAnalog=FIO_int_rep)

    if 210 or 211 or 240 or 241 in special_channels.keys(): 
        d.configIO(EnableCounter0=True)
    if 210 or 240 in special_channels.keys():
        u3.Counter0(Reset=True)
    if 211 or 241 in special_channels.keys():
        u3.Counter1(Reset=True)

    if is_verbose:
        print("Configuring U3 stream ... \n")

    # See https://labjack.com/support/datasheets/u3/hardware-description/ain/channel_numbers
    n_channels = []
    for input_channel in input_channels:

        if input_channel in special_channels.keys():
            # 32 means to ignore the (-) channel:
            n_channels.append(32)

        else:
            # 31 means to not ignore the (-) channel
            n_channels.append(31)

    # TODO TODO test that ScanFrequency should actually accept the frequency
    # divided by # of channels, and not the raw max scan frequency!!!
    d.streamConfig(NumChannels=len(input_channels), PChannels=input_channels,
                   NChannels=n_channels, Resolution=resolution_index,
                   ScanFrequency=scan_frequency)

    # Both of these device attributes are set in the above `d.streamConfig` call:
    samples_per_request = d.streamSamplesPerPacket * d.packetsPerRequest

    # TODO TODO test whether rhs should be max_scan_freq or scan_frequency:
    request_s = samples_per_request * (1 / max_scan_freq)
    if duration_s is not None:
        n_requests = int(math.ceil(duration_s / request_s))
    else:
        n_requests = None

    # Time it takes to sample all the requested input channels:
    all_channel_sample_dt = 1 / scan_frequency

    if is_verbose:
        print(f"samples_per_request: {samples_per_request}")
        print(f"samples_per_request / len(input_channels): {samples_per_request / len(input_channels)}")
        print(f"n_requests: {n_requests}")
        print(f"max_scan_freq: {max_scan_freq}")
        print(f"max_scan_freq / len(input_channels): {max_scan_freq / len(input_channels)}")
        print(f"duration_s: {duration_s}\n")
        # Because we need the last request to finish, even if it would bring our
        # sample total above the total we are effectively requesting with duration_s:
        if duration_s is not None:
            actual_duration_s = request_s * n_requests
            print(f"actual_duration_s: {actual_duration_s}")
            print(f"all_channel_sample_dt: {all_channel_sample_dt}\n")

    channel_names = [get_channel_name(d, i) for i in sorted(input_channels)]
    channel_names = [channel_name.replace("FIO", "AIN") for channel_name in channel_names]

    if input_channel_names is None:
        column_names = channel_names
    else:
        column_names = [input_channel_names[i] for i in input_channels]

    channel2column_names = dict(zip(channel_names, column_names))

    if times == "absolute":
        column_names += ["datetime"]
    elif times == "elapsed":
        column_names += ["elapsed time (s)"]
    else:
        raise ValueError("`time` value not valid. Please input either 'absolute' or 'elapsed'.")
        

    # Starting from 0 within each request. Time offset will be added to this
    # before they are written to CSV rows along with measured data.
    # If we start at 0 and use the same step, the stop will be
    # request_s - all_channel_sample_dt.
    request_times = np.arange(start=all_channel_sample_dt,
                                stop=(request_s + all_channel_sample_dt),
                                step=all_channel_sample_dt)
                                
    # TODO: This assertion only holds for non-counter/timer cases ... figure out correct assertion otherwise 
    if 224 not in input_channels:
        assert (len(request_times) == int(samples_per_request / len(input_channels)))
        
    last_time_s = 0.0
    t_start = datetime.now()

    if is_verbose:
        print("column_names:", column_names)
        print("channel2column_names:", channel2column_names)

    if not do_overwrite and os.path.exists(csv_path):
        raise IOError(f"csv_path={csv_path} already exists and `do_overwrite` is set to False!")

    # Can't use the 3rd party `future` library `open` to add the `newline`
    # argument for python2, because then `writeheader()` (and probably other
    # write calls) fail with:
    # `TypeError: write() argument 1 must be unicode, not str`
    # csv docs recommend `newline=''` for proper behavior in a few edge cases.
    if sys.version_info >= (3, 0):
        open_kwargs = dict(newline='')
    else:
        open_kwargs = dict()

    csv_file_handle = open(csv_path, "w", **open_kwargs)
    atexit.register(csv_file_handle.close)

    csv_writer = csv.DictWriter(csv_file_handle, fieldnames=column_names)
    csv_writer.writeheader()

    # Without *both* of these global definitions, _finish_up changes inside the
    # signal handler won't apply to the instance of this variable defined
    # outside of the handler. If this were Python3, I could probably use
    # nonlocal instead.
    # Initially I thought the `init_node` call in the wrapper would need
    # `disable_signals=True` in order for this to work, but this handler does
    # indeed work without that kwarg. I suppose it's happening in addition to
    # ROS signal handling?
    global _finish_up
    _finish_up = False
    def signal_shutdown(sig, frame):
        global _finish_up
        _finish_up = True
        print("Breaking out of stream ...")

    signal.signal(signal.SIGINT, signal_shutdown)

    d.streamStart()
    atexit.register(d.streamStop)

    if is_verbose:
        start = datetime.now()
        print(f"Start time is {start}")

    # Start trigger:
    if external_trigger is not None:
        print("Starting external trigger ...")
        trig.start()   
        print("Started external trigger.")

    missed = 0
    request_count = 0
    packet_count = 0
    for r in d.streamData():
        
        if r is not None:

            if r["errors"] != 0:
                warnings.warn(f"Errors counted: {r['errors']} ; {datetime.now()}")

            if r["numPackets"] != d.packetsPerRequest:
                warnings.warn(f"----- UNDERFLOW : {r['numPackets']} ; {datetime.now()}")

            if r["missed"] != 0:
                missed += r["missed"]
                warnings.warn(f"+++ Missed {r['missed']}")

            # TODO only data not used is 'firstPacket':
            # "The PacketCounter value in the first USB packet."
            # is this useful? how?

            # TODO probably warn (first time) if `r` comes back with more keys
            # than those we expect from `channel_names` (after removing the keys
            # that are always there from consideration)
            # TODO also test that channel_names agree w/ contents of `r` for the
            # FIO<x> pins on U3-HV

            row_data_lists = [r[s] for s in channel_names]

            if times == "absolute":
                
                increment_by = list(request_times + last_time_s)
                datetimes = [t_start + timedelta(0, t) for t in increment_by] 
                row_data_lists.append(datetimes)  

            elif times == "elapsed":
                row_data_lists += [list(request_times + last_time_s)]            
                
            last_time_s += request_s

            row_dicts = [dict(zip(column_names, row)) for row in zip(*tuple(row_data_lists))]
            csv_writer.writerows(row_dicts)

            request_count += 1
            packet_count += r["numPackets"]

            if (_finish_up or (n_requests is not None and request_count >= n_requests)):

                break
            
        else:
            # Got no data back from our read.
            # This only happens if your stream isn't faster than the USB
            # read timeout, ~1 sec.
            # TODO should i be warning / erring in this case?
            print(f"No data ; {datetime.now()}")

    print("Ended stream.\n")

    if is_verbose:

        stop = datetime.now()
        sampleTotal = packet_count * d.streamSamplesPerPacket
        scanTotal = sampleTotal / len(input_channels)

        print(f"{request_count} requests with {float(packet_count) / request_count} packets per request with {d.streamSamplesPerPacket} samples per packet = {sampleTotal} samples total.")
        print(f"{missed} samples were lost due to errors.")

        sampleTotal -= missed

        print(f"Adjusted number of samples = {sampleTotal}")
        print(f"sampleTotal * all_channel_sample_dt = {sampleTotal * all_channel_sample_dt}")

        runTime = ((stop-start).seconds + float((stop-start).microseconds) / 1000000)

        # TODO why does this difference seem to depend on
        # actual_duration_s?  does that mean that the timing between
        # samples is wrong in some places, or just that the startup /
        # shutdown of the stream takes longer in some cases? how to
        # test? maybe measure a reference square wave ~2-4x slower than
        # sample rate?
        
        if duration_s is not None:
            print(f"runTime - actual_duration_s: {runTime - actual_duration_s}")

        print(f"The experiment took {runTime} seconds.")
        print(f"Actual Scan Rate = {scan_frequency} Hz")

        # TODO TODO what causes discrepancies between these and
        # requested scan rate? should i warn if there's enough of a
        # difference? important? any offset between values yielded by
        # streamData, or just at beginning / end?
        # TODO test again now that break doesn't wait for one un-used yield
        # of the stream object
        
        print(f"Timed Scan Rate = {scanTotal} scans / {runTime} seconds = {float(scanTotal)/runTime} Hz")
        print(f"Timed Sample Rate = {sampleTotal} samples / {runTime} seconds = {float(sampleTotal)/runTime} Hz \n")

    # The atexit handlers will run after the labjack node that calls this
    # function exits. Letting SIGTERM (or maybe even un-handled SIGINT?) kill
    # this process would not have the handlers run.  Not calling `sys.exit`
    # here, because that prints something to ROS output.


def main():

    parser = argparse.ArgumentParser(description=__doc__, 
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_path", 
        help="Path to which to stream the .csv.")
    parser.add_argument("duration",
        help="Duration (s) of the DAQ stream. If None, will stream until exited (ctrl+c).")
    parser.add_argument("times",
        help="Accepts either 'elapsed' (default) or 'absolute'. If 'elapsed', \
        a column, 'time (s)', will be added to the .csv with time in seconds from \
        beginning of streaming. If 'absolute', a column, 'datetime' will be added \
        to the .csv with time as a string from a datetime object. N.B. Understand \
        that the offset between streaming start /s top and when those calls are \
        made are hard to predict or measure, and so using elapsed times is often \
        recommended.")

    args = parser.parse_args()
    
    csv_path = args.csv_path
    duration = args.duration
    times = args.times

    # TODO : Don't run more than one counter and/or timer. The required multiple 224 
    # channels means I have to make some fixes.
    # See: https://labjack.com/support/datasheets/u3/operation/stream-mode/digital-inputs-timers-counters

    if duration.lower() == "none":
        duration = None
    else:
        duration = float(duration)
    
    if times != "elapsed" and times != "absolute":
        raise ValueError("`times` must be either 'elapsed' or 'absolute'.")

    stream_to_csv(csv_path, 
                  duration_s=duration,
                  input_channels=[0, 210, 224], # 7 is an FIO, and so will be LOW voltage on U3-HV
                  input_channel_names={0: "PID (V)", 210: "DAQ count", 224: "16-bit roll-overs"},
                  times="absolute",
                  external_trigger=None,
                  do_overwrite=True, 
                  is_verbose=True)


if __name__ == '__main__':
    main()