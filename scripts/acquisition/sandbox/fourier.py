#!/usr/bin/env python3

import numpy as np
import matplotlib.pyplot as plt
import scipy.signal as sps

# Return the smallest power of 2 greater than or equal to a number
def expceil(x, a=2):

    temp = np.log(x)/np.log(a)
    return a**np.ceil(temp)

# Take the fourier transform of the windowed input function
# Return amplitude, phase, and frequency-spacing
def fft(ft, t, pad=0, window=None, hilbert=False, post=False):

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


if __name__ == '__main__':

    gauss = lambda x, x0, s: np.exp(-(x-x0)**2/(2*s**2))
    t = np.arange(0, 10, 0.1)
    ft = 2*np.sin(2*2*np.pi*t) + np.sin(6*2*np.pi*t)
    ft = np.sin(2*np.pi*t)

    # Calculate fft & ifft
    (ff, f) = fft(ft, t, pad=4, window=None)
    (amp, phase, f) = fft(ft, t, pad=4, window=None, post=True)
    (ft2, t2) = ifft(ff, f, pad=0, window=None)

    # Postprocess ifft
    ft2 = ft2[t2>=0]
    t2 = t2[t2>=0]
    ft2 = ft2.real

    plt.subplot(311)
    plt.plot(t, ft)
    plt.subplot(312)
    plt.plot(f, amp)
    plt.subplot(313)
    plt.plot(t2, ft2)
    plt.show()