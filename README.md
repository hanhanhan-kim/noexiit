# NOEXIIT
> "*Hell is other [insects].*"
>
> \- Insects

NOEXIIT, or *NOvel Ethological X-Insect Interaction Task*, is a behaviour rig for presenting an ethological stimulus to an insect tethered on a floating ball. We originally developed NOEXIIT to present different kinds of pinned insects to a tethered walking beetle. 

This repository houses the software for controlling NOEXIIT. It is  a `pip`-installable Python package and is a CLI. It includes commands for calibrating and testing the rig, as well as commands for acquiring experimental data. I have tested the NOEXIIT CLI on Ubuntu 18.04. 

In addition to the CLI software, the repository features a `hardware/` directory, which contains all necessary custom design files, datasheets, a bill of materials, and assembly tips. 

## Installation:



## Dependencies:

### Spinnaker 

I use FLIR Blackfly S cameras (BFS-U3-04S2M-CS) and Spinnaker 1.27.0.48 for Ubuntu 18.04. This Spinnaker version is no longer available on the FLIR website and requires e-mailing FLIR customer support.  

### FicTrac

See [Richard Moore's official repo](https://github.com/rjdmoore/fictrac) for additional details. My cloned repo is rolled back to commit `f60cae42ec747ad8e050f46079b49df2f7698749`. I use the following dependencies:

- `vcpkg` rolled back to commit `85211f3ab66e15c7669a1c14a25564afcf31e2e6`. 
- [cmake v.3.15.0](https://github.com/Kitware/CMake/releases/tag/v3.15.0).

### LabJack U3 DAQ

I use the LabJack U3 as my DAQ, which synchronizes my data streams in hardware. I use Python 3 to interface with the LabJack U3. Instructions for installing the `exodriver` library  necessary for using the LabJack U3 are available [here](https://labjack.com/support/software/installers/exodriver). Instructions for installing the LabJack U3 Python3 module are available on the [official LabJack GitHub](https://github.com/labjack/LabJackPython). 

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