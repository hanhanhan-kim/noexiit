import datetime
import time
import datetime
import sys 
import subprocess
import threading
import signal
import os

import yaml
import pandas as pd
import matplotlib.pyplot as plt

from autostep import Autostep
from camera_trigger import CameraTrigger
from switchx7 import SwitchX7 
import noexiit.utils as utils
import noexiit.move_and_get as move_and_get
from noexiit.init_BIAS import init_BIAS
from noexiit.sniff_puff_and_stream import control_valves


def main(config):

    # SET UP PARAMETERS-----------------------------------------------------------------------------------------

    # Set up autostep motors, change as necessary:
    motor_port = '/dev/ttyACM0' 
    stepper = Autostep(motor_port)
    stepper.set_step_mode('STEP_FS_128') 
    stepper.set_fullstep_per_rev(200)
    stepper.set_kval_params({'accel':30, 'decel':30, 'run':30, 'hold':30})
    stepper.set_jog_mode_params({'speed':60, 'accel':100, 'decel':1000}) # deg/s and deg/s2
    stepper.set_move_mode_to_jog()
    stepper.set_gear_ratio(1)
    stepper.enable() 

    # Specify BIAS params:
    cam_ports = ['5010', '5020', '5030', '5040', '5050']
    config_path = 'mnt/more_vids/config_jsons/trig_1200us_10secs.json' # alt is 4mins

    # Set up user arguments from config:
    duration = config["expt-pt-to-pt"]["duration"]
    trigger_port = config["expt-pt-to-pt"]["trigger_port"]
    cam_hz = config["expt-pt-to-pt"]["cam_hz"]
    # Motor stuff:
    poke_speed = config["expt-pt-to-pt"]["poke_speed"]
    ext_wait_time = config["expt-pt-to-pt"]["ext_wait_time"]
    retr_wait_time = config["expt-pt-to-pt"]["retr_wait_time"]
    posns = config["expt-pt-to-pt"]["positions"]
    ext_angle = config["expt-pt-to-pt"]["extension"]
    # Valve stuff:
    puff_port = config["expt-pt-to-pt"]["puff_port"]
    pre_puff_durn = config["expt-pt-to-pt"]["pre_puff_durn"]
    puff_durn = config["expt-pt-to-pt"]["puff_durn"]
    post_puff_durn = config["expt-pt-to-pt"]["post_puff_durn"]
    on_valve_id = config["expt-pt-to-pt"]["on_valve_id"]
    off_valve_id = config["expt-pt-to-pt"]["off_valve_id"]

    if not isinstance(duration, type(None)):
        duration = float(duration)

    if poke_speed < 10:
        raise ValueError("The poke_speed must be 10 or greater.")

    if ext_angle is None:
        with open("config.yaml") as f:
            ext_angle = yaml.load(f, Loader=yaml.FullLoader)["calibrate"]["max_ext"]
    
    # Check that motor or valve stim durations don't exceed the expt duration: 
    time_spent_rotating = move_and_get.get_time_from_pt_to_pt(stepper, posns, "jog")
    motor_duration = len(posns) * (ext_wait_time + retr_wait_time) + time_spent_rotating
    valve_duration = pre_puff_durn + puff_durn + post_puff_durn 
    if (motor_duration and valve_duration) > duration:
        raise ValueError("The time it takes for either the motors to finish moving or "
                        "for the valves to finish energizing exceeds the experiment's "
                        "recording duration. The stimulus activity should finish "
                        "before the total recording duration.")

    # Set up filename to save:
    t_script_start = datetime.datetime.now()
    name_script_start = t_script_start.strftime("%Y_%m_%d_%H_%M_%S")
    file_ending = name_script_start + ".csv"
    with open ("config.yaml") as f:
        output_dir = yaml.load(f, Loader=yaml.FullLoader)["calibrate"]["output_dir"]

    # Save the motor settings: 
    fname = f"{output_dir}motor_settings_{name_script_start}.txt"
    servo_msg = f"\nlinear servo parameters \n-------------------------- \nmax extension angle: {ext_angle}\n"
    move_and_get.save_params(stepper, fname)
    # Write:
    with open(fname, "a") as f:
        print(servo_msg, file=f)
    # Print:
    with open(fname) as f:
        print(f.read())
    
    # Set up thread for getting motor commands;
    # (can't be a subprocess, because I can create only one Autostep object):
    if duration != None:
        get_motors_duration = duration + 0.2 # needs the delay so trigger doesn't end after motor stream; also can't add fl to None
    else:
        get_motors_duration = duration 
    get_motors_thread = threading.Thread(target=move_and_get.stream_to_csv, 
                                            args=(stepper, f"{output_dir}o_loop_motor_{file_ending}", 
                                            get_motors_duration))
    get_motors_thread.daemon = True

    # Set up trigger:
    trig = CameraTrigger(trigger_port) 
    trig.set_freq(cam_hz) # frequency (Hz)
    trig.set_width(10) # (us)
    trig.stop()

    # Initializing the CameraTrigger takes 2.0 secs:
    print("Initializing the external trigger ...")
    time.sleep(2.0)
    print("Initialized external trigger.")

    # Wrap trig.stop() with prints, so prints get called in thread timer, when duration is not None:
    def stop_trigger():
        print("Stopping external trigger ...")
        trig.stop()
        print("Stopped external trigger.")

    # Write exit function:
    def stop_remaining_hardware(sig, frame):
        if duration != None:
            print("Stopping timer for trigger end.")
            trig_timer.cancel()
            print("Stopped timer for trigger end.")
        move_and_get._moving_motors = False
        print("Stopped movements.")
        if puff_port != None:
            print("De-energizing valves.")
            switch = SwitchX7(port=puff_port, timeout=1.0)
            switch.set_all(False)
            print("De-energized the valves.")
        stop_trigger()
        print("Stopping the motor commands stream to csv ...")
        move_and_get._getting_motors = False 
        print("Stopped the motor command stream to csv.")
        print("Stopping the DAQ stream process ...")
        time.sleep(1.0) # Sleep for a bit, so the DAQ stops after the get motors thread
        os.kill(p_daq.pid, signal.SIGINT) # DAQ process must die on SIGINT to exit correctly
        time.sleep(0.2) # Sleep for a bit so the print statements appear in the right order 
        if not p_daq.poll():
            print("Stopped the DAQ stream process.")
        sys.exit(0)

    signal.signal(signal.SIGINT, stop_remaining_hardware)

    # EXECUTE--------------------------------------------------------------------------------------------------

    # Initialize BIAS, if desired:
    proceed = utils.ask_yes_no("Initialize BIAS? That is, connect cams, load jsons, and start capture?", default="no")
    if proceed:
        init_BIAS(cam_ports=cam_ports, config_path=config_path)
    else:
        print("Skipping BIAS initialization ...")

    # Home the motors:
    move_and_get.home(stepper)

    # Proceed with experimental conditions once the home is set to 0:
    if stepper.get_position() == 0:

        # Move to first stepper position prior to data acquisition:
        print("Moving to starting stepper position.")
        stepper.move_to(posns[0])
        stepper.busy_wait()
        print("Moved to starting stepper position.")
        
        # START DAQ stream of PID values and counts (trigger not called here):
        dirname = os.path.dirname(os.getcwd())
        daq_args = [sys.executable, # sys.executable calls current python
                    os.path.join(dirname, "software/noexiit/stream.py"), f"{output_dir}o_loop_daq_{file_ending}", "none", "absolute"] 
        p_daq = subprocess.Popen(daq_args) 
        time.sleep(1.0) # DAQ start-up takes a bit

        # GET MOTOR positions:
        get_motors_thread.start()  
        time.sleep(0.1) # Make sure not to start after the trigger

        # START TRIGGER:
        print("Starting external trigger ...")
        trig.start()   
        print("Started external trigger.")

        if duration != None:
            trig_timer = threading.Timer(duration, stop_trigger)
            trig_timer.start()

        # START VALVES, if using valves:
        if puff_port != None:
            valves_thread = threading.Thread(target=control_valves,
                                args=(puff_port, 
                                      pre_puff_durn, 
                                      puff_durn, 
                                      post_puff_durn, 
                                      on_valve_id, 
                                      off_valve_id))
            valves_thread.daemon = True
            valves_thread.start()
        else:
            print("No valves will be energized in this experiment.")

        # START MOTORS (is blocking):
        move_and_get.pt_to_pt_and_poke(stepper, posns, ext_angle, 
                                       poke_speed, ext_wait_time, retr_wait_time)

        # STOP EVERYTHING upon completion:
        if duration == None:
            stop_trigger()
            print("Stopping the motor commands stream to csv ...")
            move_and_get._getting_motors = False 

        get_motors_thread.join() 
        print("Stopped the motor command stream to csv.")

        valves_thread.join()
        print("Stopped the valves command stream to csv.")
        
        print("Stopping the DAQ stream process ...")
        time.sleep(1.0) # Sleep for a bit, so the DAQ stops after the get motors thread
        os.kill(p_daq.pid, signal.SIGINT) # DAQ process must die on SIGINT to exit correctly
        time.sleep(0.2) # Sleep for a bit so the print statements appear in the right order 
        if not p_daq.poll():
            print("Stopped the DAQ stream process.")
        
    # PLOT DATA---------------------------------------------------------------------------------------------
    
    # Pre-process:
    motor_df = pd.read_csv(f"{output_dir}o_loop_motor_{file_ending}")
    motor_df["datetime"] = pd.to_datetime(motor_df["datetime"], 
                                          format="%Y-%m-%d %H:%M:%S.%f")

    daq_df = pd.read_csv(f"{output_dir}o_loop_daq_{file_ending}")
    daq_df["datetime"] = pd.to_datetime(daq_df["datetime"], 
                                        format="%Y-%m-%d %H:%M:%S.%f")

    # Merge and interpolate, but only for plotting. Do NOT interpolate saved data:
    df = pd.merge_ordered(daq_df, motor_df, "datetime")
    # Interpolating on datetime objs is buggy (2021/10/25): 
    interpolated = df.loc[:, df.columns != "datetime"].interpolate()
    df = pd.concat([df["datetime"], interpolated], axis=1)
    df = utils.datetime_to_elapsed(df)

    # Plot:
    plt.style.use("ggplot")

    ax1 = plt.subplot(2, 1, 1)
    ax1.tick_params(labelbottom=False) 
    plt.title("Data aligned according to host clock")
    plt.plot(df["elapsed secs"], df["stepper position (deg)"], 
             label="stepper position (degs)")
    plt.plot(df["elapsed secs"], df["servo_0 position (deg)"], 
             label="servo_0 position (degs)")
    plt.plot(df["elapsed secs"], df["servo_1 position (deg)"], 
             label="servo_1 position (degs)")
    plt.ylabel("motor position (degs)")
    plt.legend()
    plt.grid(True)

    ax2 = plt.subplot(2, 1, 2, sharex=ax1)
    plt.plot(df["elapsed secs"], df["PID (V)"])
    plt.xlabel("time (s)")
    plt.ylabel("PID reading (V)")
    plt.grid(True)

    plt.subplots_adjust(hspace=.1)

    plt.savefig((f"{output_dir}o_loop_" + file_ending).replace(".csv", ".png"), dpi=500)
    plt.show()