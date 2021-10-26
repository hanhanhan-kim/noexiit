# NOEXIIT
> "*Hell is other [insects].*"
>
> \- Insects

NOEXIIT, or *NOvel Ethological X-Insect Interaction Task*, is a behaviour rig for presenting an ethological stimulus to an insect tethered on a floating ball. We originally developed NOEXIIT to present different kinds of pinned insects to a tethered walking beetle. 

This repository houses the software for controlling NOEXIIT. It is  a `pip`-installable Python package by the same name and is a CLI. It includes commands for calibrating and testing the rig, as well as commands for acquiring experimental data. I have tested the NOEXIIT CLI on Ubuntu 18.04. 

In addition to the CLI software, the repository features a `hardware/` directory, which contains all necessary custom design files, datasheets, a bill of materials, and assembly tips. 

## Installation:

1. Clone this repository:

   ```bash
   git clone https://github.com/hanhanhan-kim/noexiit
   ```

2. Install the Anaconda environment from the repo's root directory, where `conda_env.yaml` is housed:

   ```bash
   conda env create -f conda_env.yaml
   ```

   It will create an environment called `noexiit`.

3. Activate the environment:

   ```bash
   conda activate noexiit
   ```

4. Install the `noexiit` Python package from the repo's `software/` subdirectory:

   ```bash
   pip install -e .
   ```

## Dependencies:

In addition to the `noexiit` Python package installation, additional non-Python software and firmware must be installed. They are as follows:

### Spinnaker 

I use FLIR Blackfly S cameras (BFS-U3-04S2M-CS) and Spinnaker 1.27.0.48 for Ubuntu 18.04. This Spinnaker version is no longer available on the FLIR website and requires e-mailing FLIR customer support.  

### FicTrac

See [Richard Moore's official repo](https://github.com/rjdmoore/fictrac) for additional details. My cloned repo is rolled back to commit `f60cae42ec747ad8e050f46079b49df2f7698749`. I use the following dependencies:

- `vcpkg` rolled back to commit `85211f3ab66e15c7669a1c14a25564afcf31e2e6`. 
- [cmake v.3.15.0](https://github.com/Kitware/CMake/releases/tag/v3.15.0).

### LabJack U3 DAQ

I use the LabJack U3-HV as my DAQ, which synchronizes my data streams in hardware.  Instructions for installing the `exodriver` library necessary for using the LabJack U3-HV are available [here](https://labjack.com/support/software/installers/exodriver).  I use LabJack's [Python module](https://github.com/labjack/LabJackPython) to interface with the LabJack U3-HV. Set up of the Anaconda environment already installs the LabJack Python module.

### Firmware

#### Multi-camera external trigger

[My fork](https://github.com/hanhanhan-kim/autostep) of [Will Dickson's official `camera_trigger` repo](https://github.com/willdickson/camera_trigger) requires firmware dependencies on an ATmega328P MCU. I use the following Arduino IDE dependencies:

- TimerOne v1.1.0
- Streaming v5.0.0
- ArduinoJson v5.13.5 (is _not_ compatible with v6.0.0+)
- Array v1.1.2 

Set up of the Anaconda environment already installs the software dependencies for [`camera_trigger`](https://github.com/hanhanhan-kim/autostep).

#### Stepper and servo motors

[My fork](https://github.com/hanhanhan-kim/autostep) of [Will Dickson's official `autostep` repo](https://github.com/willdickson/autostep) requires firmware dependencies on a Teensy 3.2 MCU. Uploading firmware onto a Teensy requires the [Teensyduino add-on for the Arduino IDE](https://www.pjrc.com/teensy/teensyduino.html). I use the following Arduino IDE dependencies:

- Streaming v5.0.0
- ArduinoJson v5.13.5 (is _not_ compatible with v6.0.0+)
- Array v1.1.2
- [SparkFun's L6470 AutoDriver library](https://github.com/sparkfun/L6470-AutoDriver/tree/master/Libraries/Arduino) (commit `734489ea1eaeb96cfab712c96817e35d9c942eb8`).

Set up of the Anaconda environment already installs the software dependencies for [`autostep`](https://github.com/hanhanhan-kim/autostep).

#### Valves

[My fork](https://github.com/hanhanhan-kim/switchx7) of [Will Dickson's official `switchx7` repo](https://github.com/willdickson/switchx7) requires firmware dependencies on a Teensy 3.2 MCU. Uploading firmware onto a Teensy requires the [Teensyduino add-on for the Arduino IDE](https://www.pjrc.com/teensy/teensyduino.html). I use the following Arduino IDE dependencies:

- Streaming v5.0.0

Set up of the Anaconda environment already installs the software dependencies for [`switchx7`](https://github.com/hanhanhan-kim/switchx7).

## How to use:

Using `noexiit` is simple! From anywhere, type the following in the command line:

```bash
noexiit
```

Doing so will bring up the menu of possible options and commands. To execute a command, specify the command of interest after `noexiit`. For example, to run the `print-config` command:

```bash
noexiit print-config
```

### The `.yaml` file

The successful execution of a command requires filling out a single `.yaml` configuration file. The configuration file provides the arguments for all of `noexiit`'s commands. By default, `noexiit` will look for a file calleld `config.yaml` in the directory from which you run a `noexiit` command. For this reason, I suggest that you name your `.yaml` file `config.yaml`. Otherwise, you can specify a particular `.yaml` file like so:

```bash
noexiit --config <path/to/config.yaml> <command>
```

For example, if the `.yaml` file you want to use has the path `~/tmp/my_weird_config.yaml`, and you want to run the `pt-to-pt` command, you'd input:

```bash
noexiit --config ~/tmp/my_weird_config.yaml pt-to-pt
```

Each key in the `.yaml` configuration file refers to a `noexiit` command. The value of each of these keys is a dictionary that specifies the parameters for that `vidtools` command. Make sure you do not have any trailing spaces in the `.yaml` file. An example `config.yaml` file is provided in the repository. 

### Commands

The outputs of `noexiit`'s commands never overwrite existing files, without first asking for user confirmation. `noexiit`'s commands and their respective `.yaml` file arguments are documented below:

#### `print-config`

<details><summary> Click for details. </summary>
<br>

This command prints the contents of the `.yaml` configuration file. It does not have any `.yaml` parameters.
</details>


#### `plot-pid-live`

<details><summary> Click for details. </summary>
<br>

This command plots and saves to a `.csv`, in real time, the voltage readings of the photo-ionization detector (PID). It assumes that the PID is connected to the **AIN 7** (low-voltage FIO) pin of the LabJack U3-HV . It uses a 'command and response' protocol, instead of a 'streaming' protocol. This command is useful for troubleshooting the PID, and is not recommended for experimental data acquisition. It does not have any `.yaml` parameters. 
</details>


#### `calibrate`

<details><summary> Click for details. </summary>
<br>

This command calibrates the linear servo's behaviour. It sets the servo's maximum extension angle to avoid crashes and overshoots, based on visual inspection. The servo can rotate around the rig's spherical treadmill, while being held at the set max extension angle. This function is useful for preparing closed-loop experiments. This command can also configure the acquired experimental data to a specific directory. Importantly, this command does not require the user to update the `config.yaml` file beforehand. Rather, the command updates the configuration file based on 'real-time' user inputs. Alternatively, this command does not need to be run, and the `config.yaml` file can be manually modified. This command's `.yaml` parameters are:

- `max_ext` (float): The max extension value of the linear servo(s). Must be a value between 0.0 and 180.0, inclusive. Running the `calibrate` command will automatically update this value.

- `output_dir` (string): The path to the directory where acquired data will be saved. Running the `calibrate` command can automatically update this value.
</details>


#### `expt-pt-to-pt`

<details><summary> Click for details. </summary>
<br>

This command moves the tethered stimulus to each angular position in a list of specified positions. Upon arriving at a position, the command extends the tethered stimulus for a fixed duration. Then retracts the tethered stimulus for a fixed duration. Streams data during motor movements. Events happen in the following order:

Initialization (homing, etc.)
│
├── Gets DAQ stuff
├── Gets motors' positions
├── Starts cam trigger
├── Starts motors
│
├── Finishes motors or duration
├── Stops cam trigger
├── Stops getting motors' positions
└── Stops getting DAQ stuff

Events happen in the above order even when the command is interrupted (ctrl + c).

"DAQ stuff" refers to the PID data and the frame counter. Motor position sets and gets happen in a different process from DAQ gets, in order to achieve maximum frequencies. 

This command's `.yaml` parameters are: 

- `duration` (float or `null`): Duration (secs) of the synchronized multi-cam video recordings. If set to `null`, will record until the motor sequence has finished. If using BIAS, the user MUST match this argument to the BIAS recordings' set duration. 

- `poke_speed` (integer): A scalar speed factor for the tethered stimulus' extension and retraction. Must be positive. 10 is the fastest. Higher values are slower. 

- `ext_wait_time` (float): Duration (secs) for which the tethered stimulus is extended at each set angular position. 

- `retr_wait_time` (float): Duration (secs) for which the tethered stimulus is retracted at each set angular position. 

- `extension` (float or `null`): The maximum linear servo extension angle. If `null`, will inherit the value from the `calibrate` parameter in the `config.yaml` file. 
</details>


#### `expt-still-robot`

<details><summary> Click for details. </summary>
<br>

This command moves the tethered stimulus at 1) an angular velocity opposite in direction, and adjustable in magnitude, to the animal on the ball (stepper motor), and 2) to some distance away or towards the animal on the ball, given the tethered  stimulus' angular position (linear servo). The idea is to mimic a stationary  stimulus in a flat planar world. The animal turning right and away from a stimulus in front of it, in the planar world, is equivalent to the stimulus turning left and retracting away from the animal, in the on-a-ball world. This command demonstrates the closed-loop capabilities of NOEXIIT.

It assumes an ATMega328P-based camera trigger, even if as of 2021/10/25, this command operates only a single camera. 

This command's `.yaml` parameters are:

- `duration` (float): Duration (secs) of the closed-loop acquisition mode. 

- `k_stepper` (float): Gain term for modifying the significance of the animal's turns. A value of 1 means that when the animal turns theta degrees, the stimulus also rotates theta degrees, but in the opposite direction. A value less than 1 means that when the animal rotates theta degrees, the stimulus rotates less than theta degrees by a factor of `k_stepper`, and in the opposite direction. In this way, the animal's actions are 'less significant' than they normally are. A value greater than 1 means that when the animal rotates theta degrees, the stimulus rotates more than theta degrees by a factor of `k_stepper`, and in the opposite direction. In this way, the animal's actions are 'more significant' than they normally are. 

- `ball_radius` (float): Radius of the spherical treadmill, in mm. 
</details>