# NOEXIIT
> "*Hell is other [insects].*"
>
> \- Most non-myrmecophilous beetles

NOEXIIT, or *NOvel Ethological X-Insect Interaction Task*, is a behaviour rig for presenting an ethological stimulus to an insect tethered on a floating ball. We originally developed NOEXIIT to present different kinds of pinned insects to a tethered walking beetle. 

## Dependencies
I use Ubuntu LTS 18.04. 

### Python
_Python 3.6.9_
```
astroid==2.3.3
autostep==0.0.0
camera-trigger==0.0.0
cycler==0.10.0
isort==4.3.21
kiwisolver==1.1.0
lazy-object-proxy==1.4.3
matplotlib==3.1.2
mccabe==0.6.1
numpy==1.18.1
pandas==0.25.3
pylint==2.4.4
pyparsing==2.4.6
pyserial==3.4
python-dateutil==2.8.1
pytz==2019.3
scipy==1.4.1
six==1.13.0
typed-ast==1.4.0
wrapt==1.11.2
```

### Multi-camera external trigger firmware dependencies
See [Will Dickson's official repo](https://github.com/willdickson/camera_trigger) for additional details. My cloned repo is rolled back to commit `da8570642aa36987b56101a6618d0b61ba8d11b0`. The firmware requires an ATmega328P MCU. I use the following Arduino IDE dependencies:
- TimerOne v1.1.0
- Streaming v5.0.0
- ArduinoJson v5.13.5 (is _not_ compatible with v6.0.0+)
- Array v1.1.2 

### Motor firmware dependencies
See [Will Dickson's official repo](https://github.com/willdickson/autostep) for additional details. The firmware requires a Teensy 3.2 MCU and the [Teensyduino add-on for the Arduino IDE](https://www.pjrc.com/teensy/teensyduino.html). My cloned repo is rolled back to commit `444fdabf883b54d7669cbc3888e8d0a3f6f0d73d`. I use the following Arduino IDE dependencies:
- Streaming v5.0.0
- ArduinoJson v5.13.5 (is _not_ compatible with v6.0.0+)
- Array v1.1.2
- [SparkFun's L6470 AutoDriver library](https://github.com/sparkfun/L6470-AutoDriver/tree/master/Libraries/Arduino) (commit `734489ea1eaeb96cfab712c96817e35d9c942eb8`).

### Spinnaker 

I use FLIR Blackfly S cameras (BFS-U3-04S2M-CS) and Spinnaker 1.27.0.48 for Ubuntu 18.04. This Spinnaker version is available for download [here](https://flir.app.boxcn.net/v/SpinnakerSDK/folder/74729115388). 

### FicTrac

See [Richard Moore's official repo](https://github.com/rjdmoore/fictrac) for additional details. My cloned repo is rolled back to commit `f60cae42ec747ad8e050f46079b49df2f7698749`. I use the following dependencies:
- `vcpkg` rolled back to commit `85211f3ab66e15c7669a1c14a25564afcf31e2e6`. 
- [cmake v.3.15.0](https://github.com/Kitware/CMake/releases/tag/v3.15.0).
