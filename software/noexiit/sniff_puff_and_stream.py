import time
import threading
import atexit
from os.path import expanduser, join
from noexiit.utils import ask_yes_no

from switchx7 import SwitchX7 
from noexiit.stream import stream_to_csv


def control_valves(port: str, 
                   pre_stim_durn: float, stim_durn: float, post_stim_durn: float, 
                   on_valve_id: int, off_valve_id: int):

    """
    Activates only an 'OFF' valve (e.g. solvent) for a duration, 
    then only an 'ON' valve (e.g. odour) for a duration, and then 
    only an 'OFF' valve (e.g. solvent) for a duration. 

    Parameters:
    -----------
    port (str): The path to the Teensy MCU port, 
        e.g. /dev/ttyACM1.
    pre_stim_durn (float): The time (secs) before 
        activating only the 'ON' valve.
    stim_durn (float): The time (secs) during the 
        activation of only the 'ON' valve.
    post_stim_durn (float):The time (secs) after 
        activating only the 'ON' valve. 
    on_valve_id (int): The ID of the 'ON' valve. 
        Will be a value between 0 and 6 inclusive.
    off_valve_id (int): The ID of the 'OFF' valve. 
        Will be a value between 0 and 6 inclusive. 
    """
    
    valve_ids = list(range(6))

    if (on_valve_id or off_valve_id) not in valve_ids:
        raise ValueError(f"Either valve {on_valve_id} "
                         f"or valve {off_valve_id} are not "
                          "in the possible valve IDs.")

    switch = SwitchX7(port=port, timeout=1.0)

    print(f"valve {off_valve_id} only: solvent")
    switch.set(off_valve_id, True)
    switch.set(on_valve_id, False)
    time.sleep(pre_stim_durn)

    print(f"valve {on_valve_id} only: odour")
    switch.set(off_valve_id, False)
    switch.set(on_valve_id, True)
    time.sleep(stim_durn) 

    print(f"valve {off_valve_id} only: solvent")
    switch.set(off_valve_id, True)
    switch.set(on_valve_id, False)
    time.sleep(post_stim_durn)


def main(config):
    
    duration = config["sniff-and-puff"]["duration"]
    output_dir = config["sniff-and-puff"]["output_dir"]

    port = config["sniff-and-puff"]["port"]
    pre_stim_durn = config["sniff-and-puff"]["pre_stim_durn"]
    stim_durn = config["sniff-and-puff"]["stim_durn"]
    post_stim_durn = config["sniff-and-puff"]["post_stim_durn"]
    on_valve_id = config["sniff-and-puff"]["on_valve_id"]
    off_valve_id = config["sniff-and-puff"]["off_valve_id"]

    if not isinstance(duration, type(None)):
        duration = float(duration)
    if isinstance(output_dir, type(None)):
        output_dir = expanduser(config["calibrate"]["output_dir"])

    expt_durn = pre_stim_durn + stim_durn + post_stim_durn

    if isinstance(duration, type(None)):
        lengthen_stream = ask_yes_no("The duration of the total streaming time "
                                     "is `None`. Do you want to lengthen the "
                                     "total streaming time to the length of the "
                                     "experiment? If not, you will be recording "
                                     "the stream until it's exited (ctrl+c).",
                                     default="no")

    else:
        if expt_durn > duration:
            lengthen_stream = ask_yes_no("The sum of the pre-stim, stim, "
                                "and post-stim durations "
                                "is greater than the total data streaming time. "
                                "Do you want to lengthen the total data streaming time "
                                "to the length of the experiment?",
                                default="yes")
            
    if lengthen_stream:
        duration = expt_durn
    

    def exit_safely(port=port):
        switch = SwitchX7(port=port, timeout=1.0)
        switch.set_all(False)
    atexit.register(exit_safely)


    fname = "sniffed_puffed.csv"
    csv_path = join(output_dir, fname)

    # TODO : Don't run more than one counter and/or timer. The required multiple 224 
    # channels means I have to make some fixes.
    # See: https://labjack.com/support/datasheets/u3/operation/stream-mode/digital-inputs-timers-counters

    # Operate valves: 
    valves_thread = threading.Thread(target=control_valves, 
                                     args=(port, 
                                           pre_stim_durn, 
                                           stim_durn, 
                                           post_stim_durn, 
                                           on_valve_id, 
                                           off_valve_id))
    valves_thread.daemon = True
    valves_thread.start()

    # Start the DAQ stream:
    stream_to_csv(csv_path=csv_path, 
                  duration_s=duration,
                  input_channels=[ # FIOs 4-7 will be LOW voltage AIN on U3-HV
                                    # 3,
                                    7, 
                                    193, 
                                    # 210, 
                                    # 224
                                 ], 
                  input_channel_names={
                                        # 3: "PID (V)", 
                                        7: "PID (V)", 
                                        193: "digi_valves",
                                        # 210: "DAQ count", 
                                        # 224: "16-bit roll-overs"
                                      },
                #   FIO_digital_channels=[4,5,6,8,9,10,11,12,13,14,15], # I don't NEED to specify this; 7 is excluded because it's PID, must be analog 
                  times="absolute",
                  do_overwrite=True, 
                  is_verbose=True)