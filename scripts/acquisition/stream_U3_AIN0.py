#!/home/platyusa/anaconda3/envs/behaviour/bin/python

import sys
import traceback
from datetime import datetime
import time
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

import u3
import u6
import ue9

duration =  60.0
# num_channels = 1
# SCAN_FREQUENCY is the scan frequency of stream mode in Hz
SCAN_FREQUENCY = 5000
# num_samples = (duration * SCAN_FREQUENCY) 
# MAX_REQUESTS is the number of packets to be read.
# MAX_REQUESTS = int(round(num_samples/48))
# MAX_REQUESTS = 75 
MAX_REQUESTS = int(round(duration * SCAN_FREQUENCY / 1200)) # to record for 10 s

d = None

###############################################################################
# U3
# Uncomment these lines to stream from a U3
###############################################################################

# At high frequencies ( >5 kHz), the number of samples will be MAX_REQUESTS
# times 48 (packets per request) times 25 (samples per packet).
d = u3.U3()

# To learn the if the U3 is an HV
d.configU3()

# For applying the proper calibration to readings.
d.getCalibrationData()

# Set the FIO0 and FIO1 to Analog (d3 = b00000011)
d.configIO(FIOAnalog=3)

print("Configuring U3 stream")
d.streamConfig(NumChannels=1, PChannels=[0], NChannels=[31], Resolution=3, ScanFrequency=SCAN_FREQUENCY)


###############################################################################
# U6
# Uncomment these lines to stream from a U6
###############################################################################
'''
# At high frequencies ( >5 kHz), the number of samples will be MAX_REQUESTS
# times 48 (packets per request) times 25 (samples per packet).
d = u6.U6()

# For applying the proper calibration to readings.
d.getCalibrationData()

print("Configuring U6 stream")

d.streamConfig(NumChannels=2, ChannelNumbers=[0, 1], ChannelOptions=[0, 0], SettlingFactor=1, ResolutionIndex=1, ScanFrequency=SCAN_FREQUENCY)
'''

###############################################################################
# UE9
# Uncomment these lines to stream from a UE9
###############################################################################
'''
# At 96 Hz or higher frequencies, the number of samples will be MAX_REQUESTS
# times 8 (packets per request) times 16 (samples per packet).
# Currently over ethernet packets per request is 1.
d = ue9.UE9()
#d = ue9.UE9(ethernet=True, ipAddress="192.168.1.209")  # Over TCP/ethernet connect to UE9 with IP address 192.168.1.209

# For applying the proper calibration to readings.
d.getCalibrationData()

print("Configuring UE9 stream")

d.streamConfig(NumChannels=2, ChannelNumbers=[0, 1], ChannelOptions=[0, 0], SettlingTime=0, Resolution=12, ScanFrequency=SCAN_FREQUENCY)
'''

if d is None:
    print("""Configure a device first.
Please open streamTest.py in a text editor and uncomment the lines for your device.

Exiting...""")
    sys.exit(0)

try:
    print("Start stream")
    d.streamStart()
    start = datetime.now()
    print("Start time is %s" % start)

    missed = 0
    dataCount = 0
    packetCount = 0

    num_AIN0_readings = []
    avg_AIN0_readings = []
    AIN0_readings = []
    elapsed_time = []
    t_start = time.time()

    for r in d.streamData():
        if r is not None:
            # Our stop condition
            if dataCount >= MAX_REQUESTS:
                break

            if r["errors"] != 0:
                print("Errors counted: %s ; %s" % (r["errors"], datetime.now()))

            if r["numPackets"] != d.packetsPerRequest:
                print("----- UNDERFLOW : %s ; %s" %
                      (r["numPackets"], datetime.now()))

            if r["missed"] != 0:
                missed += r['missed']
                print("+++ Missed %s" % r["missed"])

            # Comment out these prints and do something with r
            print("Average of %s    AIN0 readings: %s    Time: %s" %
                  (len(r["AIN0"]), 
                  sum(r["AIN0"])/len(r["AIN0"]), time.time() - t_start))
            
            num_AIN0_readings.append(len(r["AIN0"]))
            avg_AIN0_readings.append(sum(r["AIN0"])/len(r["AIN0"]))
            AIN0_readings.extend(r["AIN0"])
            elapsed_time.append(time.time()-t_start)

            dataCount += 1
            packetCount += r['numPackets']
        else:
            # Got no data back from our read.
            # This only happens if your stream isn't faster than the USB read
            # timeout, ~1 sec.
            print("No data ; %s" % datetime.now())
except:
    print("".join(i for i in traceback.format_exc()))
finally:
    stop = datetime.now()
    d.streamStop()
    print("Stream stopped.\n")
    d.close()

    sampleTotal = packetCount * d.streamSamplesPerPacket

    scanTotal = sampleTotal / 2  # sampleTotal / NumChannels
    print("%s requests with %s packets per request with %s samples per packet = %s samples total." %
          (dataCount, (float(packetCount)/dataCount), d.streamSamplesPerPacket, sampleTotal))
    print("%s samples were lost due to errors." % missed)
    sampleTotal -= missed
    print("Adjusted number of samples = %s" % sampleTotal)

    runTime = (stop-start).seconds + float((stop-start).microseconds)/1000000
    print("The experiment took %s seconds." % runTime)
    print("Actual Scan Rate = %s Hz" % SCAN_FREQUENCY)
    print("Timed Scan Rate = %s scans / %s seconds = %s Hz" %
          (scanTotal, runTime, float(scanTotal)/runTime))
    print("Timed Sample Rate = %s samples / %s seconds = %s Hz" %
          (sampleTotal, runTime, float(sampleTotal)/runTime))

    # Convert elapsed time to calendar time:
    t_cal_start = str(time.ctime(int(elapsed_time[0]) + t_start))
    cal_time = []
    for t in elapsed_time:
        cal_time.append(time.ctime(int(t) + t_start))

    # Save output to csv:
    df = pd.DataFrame({"Elapsed time": elapsed_time,
                       "Calendar time": cal_time, 
                       "Number of AIN0 readings": num_AIN0_readings, 
                       "Average value of AIN0 readings": avg_AIN0_readings})
    
    df.to_csv(t_cal_start + "AIN0_readings.csv", index=False)

    # Plot:
    AIN0_readings = np.array(AIN0_readings)
    AIN0_readings = AIN0_readings[AIN0_readings < 9]
    time = np.linspace(0, duration, len(AIN0_readings))
    plt.plot(time, AIN0_readings)
    plt.show()

    # plt.plot(elapsed_time, avg_AIN0_readings)
    # plt.show() 