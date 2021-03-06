#!/usr/bin/env python3

import sys
import time
import datetime
import serial
import signal
import csv

import matplotlib
import matplotlib.pyplot as plt

import u3


class LivePlot(serial.Serial):

    def __init__(self):

        # Start the DAQ counter:
        u3.Counter0(Reset=True)
        self.device = u3.U3()
        self.device.configIO(EnableCounter0=True)
        print(f"First count is pre-trigger and is 0: {self.device.getFeedback(u3.Counter0(Reset=False))[0]}")
        time.sleep(1.0) # give time to see above print

        self.num_lines = 1
        self.window_size = 10.0
        self.data_file = 'data.csv'
        self.color_list = ['b', 'r', 'g', 'm', 'c']
        self.label_list = ['sensor {}'.format(i+1) for i in range(self.num_lines)]

        self.t_init =  time.time()
        self.t_list = []
        self.list_of_data_lists = [[] for i in range(self.num_lines)]

        self.running = False
        signal.signal(signal.SIGINT, self.sigint_handler)

        plt.ion()
        self.fig = plt.figure(1)
        self.ax = plt.subplot(111) 
        self.line_list = []
        for i in range(self.num_lines):
            color_ind = i%len(self.color_list)
            line, = plt.plot([0,1], [0,1],self.color_list[color_ind])
            line.set_xdata([])
            line.set_ydata([])
            self.line_list.append(line)
        plt.grid('on')
        plt.xlabel('t (sec)')
        plt.ylabel('voltage (V)')
        self.ax.set_xlim(0,self.window_size)
        self.ax.set_ylim(-0.01, 5.01)
        plt.title("PID sensor data")
        plt.figlegend(self.line_list,self.label_list,'upper right')
        self.fig.canvas.flush_events()


    def sigint_handler(self,signum,frame):
        self.running = False

    def run(self):

        self.running = True

        csv_file_handle = open(self.data_file, "w", newline="")
        col_names = ["t (secs)", "PID"]
        csv_writer = csv.DictWriter(csv_file_handle, fieldnames=col_names)
        csv_writer.writeheader()
        
        while self.running:
            try:
                date = datetime.datetime.now()
                raw_list = [self.device.getAIN(0)] # PID V here
            except IndexError:
                continue
            except ValueError:
                continue

            # liter_per_min_list = [self.raw_to_liter_per_min(x) for x in raw_list]
            for data, data_list in zip(raw_list, self.list_of_data_lists):
                data_list.append(data)

            t_elapsed = time.time() - self.t_init
            self.t_list.append(t_elapsed)

            num_pop = 0
            while (self.t_list[-1] - self.t_list[0]) > self.window_size:
                self.t_list.pop(0)
                num_pop += 1

            for line, data_list in zip(self.line_list, self.list_of_data_lists):
                for i in range(num_pop):
                    data_list.pop(0)
                line.set_xdata(self.t_list)
                line.set_ydata(data_list)

            xmin = self.t_list[0]
            xmax = max(self.window_size, self.t_list[-1])

            self.ax.set_xlim(xmin,xmax)
            self.fig.canvas.flush_events()
            csv_writer.writerow({col_names[0]: date, 
                                    col_names[1]: raw_list[0]})

            print('{:0.2f} '.format(t_elapsed),end='')
            for val in raw_list:
                print('{:0.2f} '.format(val),end='')
            print()

        csv_file_handle.close()
        print('Successfully quitted')



# ---------------------------------------------------------------------------------------
if __name__ == '__main__':

    liveplot = LivePlot()
    liveplot.run()



