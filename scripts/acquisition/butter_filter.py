#!/usr/bin/env python3

# Written by Will Dickson:

import scipy
import numpy
import scipy.signal as signal

class ButterFilter:

    def __init__(self, cutoff_freq, filter_order, sample_rate):
        self.cutoff_freq = cutoff_freq
        self.filter_order = filter_order
        self.sample_rate = sample_rate

        self.coef_b, self.coef_a = signal.butter(
                self.filter_order, 
                self.cutoff_freq, 
                fs=self.sample_rate, 
                btype='low'
                )

        # Reverse order of coefficients for conveince
        self.coef_a = self.coef_a[::-1]
        self.coef_b = self.coef_b[::-1]

        # Initialize empty dictionary of lagged signal and filter values
        self.reset()

    def reset(self):
        self.values = {}

    def update(self, x):
        # If this is the first update initialze lagged values to first signal value
        if not self.values:
            self.values['filter'] = []
            self.values['signal'] = []
            for i in range(self.filter_order):
                self.values['filter'].append(x)
            for i in range(self.filter_order+1):
                self.values['signal'].append(x)


        # Add new filter value to stored values
        self.values['signal'].append(x)
        self.values['signal'].pop(0)

        # Compute new filtered value
        filter_vals = numpy.array(self.values['filter'])
        signal_vals = numpy.array(self.values['signal'])
        new_filter_val = (self.coef_b*signal_vals).sum() - (self.coef_a[:-1]*filter_vals).sum()
        new_filter_val /= self.coef_a[-1]

        # Add new filtered value to stored values
        self.values['filter'].append(new_filter_val)
        self.values['filter'].pop(0)
        return new_filter_val


# ----------------------------------------------------------------------------------------------------
if __name__ == '__main__':

    import matplotlib.pyplot as plt


    fcut = 2.0
    n = 10 
    fs = 100.0
    dt = 1/fs

    period = 1.0/1.5

    # Define filter:
    filt = ButterFilter(fcut, n, fs) 

    t = scipy.arange(0,1000)*dt
    x = scipy.sin(2.0*scipy.pi*t/period)
    x = x + 0.1*scipy.randn(*x.shape)

    y_list = []
    for x_val in x:
        # Apply filter:
        y_val = filt.update(x_val)
        y_list.append(y_val)
    y = numpy.array(y_list)

    plt.plot(t,x,'b')
    plt.plot(t,y,'r')
    plt.show()





        

