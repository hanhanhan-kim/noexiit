#!/usr/bin/env python3

"""
Fourier transform and inverse fourier transform offline data with helper \
functions.
Originally written by Kellan P Moorse. 

"""

import numpy as np
import scipy.signal as sps
import scipy.interpolate as spi


def expceil(x, a=2):
    """
    Return the smallest power of 2 greater than or equal to a number
    """

    temp = np.log(x)/np.log(a)
    return a**np.ceil(temp)


def fft(ft, t, pad=0, window=None, hilbert=False, post=False):
    """
    Take the fourier transform of the windowed input function. 
    Return amplitude, phase, frequency-spacing. 
    """

    # Extract sample period
    if len(t) > 0:
        dt = np.diff(t[:2])[0]
        if not np.all(np.diff(t) - dt < dt/1e6):
            raise ValueError("Sample frequency is not constant; FFT requires constant sampling")
    else:
        dt = t

    if window:
        ft = window(len(ft))*ft
    if hilbert:
        ft = sps.hilbert(ft)

    # Find power-of-two pad length and apply transform
    if pad>0:
        N = int(expceil(len(ft)*pad))
    else:

        N = len(ft)

    ff = np.fft.fft(ft, N)
    f = np.fft.fftfreq(N, dt)

    # # Separate amplitude and phase
    # amp = np.abs(ff)
    # ph = np.angle(ff)

    if post:
        ff = ff[f>=0]
        f = f[f>=0]
        amp = np.abs(ff)
        ph = np.angle(ff)
        return (amp, ph, f)
    else:
        return (ff, f)


def ifft(ff, f, pad=0, window=None):
    """
    Take the inverse fourier transform of the windowed input function.
    Return the fourier transform and time domain. 
    """

    # Extract sample period
    if len(f) > 0:
        df = np.diff(f[:2])[0]
        assert np.all(np.diff(f) - df < df/1e6)
    else:
        df = f

    if window:
        ff = window(len(ff))*ff

    if pad>0:
        N = int(expceil(len(ff)*pad))
    else:
        N = len(ff)

    ft = np.fft.ifft(ff, N)
    t = np.fft.fftfreq(N, df)

    return (ft, t)