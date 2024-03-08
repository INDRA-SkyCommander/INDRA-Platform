#!/usr/bin/env python3

import time
import yaml
import gnuradio
from gnuradio import gr
from gnuradio import analog
from gnuradio.fft import window
from gnuradio.filter import firdes
from statistics import mean
import osmosdr
from random import randint

def jam(freq, power, delay=1):
    
    print(f"\nThe frequency currently jammed is: {freq / (10e5)}MHz")
    samp_rate = 20e6  # Sample Rate
    sdr_bandwidth = 20e6  # Hackrf SDR Bandwidth
    RF_gain, IF_gain = set_gains(power)  # Hackrf SDR antenna gain

    tb = gr.top_block()

    source = analog.noise_source_c(analog.GR_GAUSSIAN, 1, 1)

    #HackRF parameters are set below. These are specific to the hackrf and are set with osmosdr.sink
    #all other supplied values are tuned for the device.

    freq_mod = analog.frequency_modulator_fc(1)
    osmosdr_sink = osmosdr.sink(
        args="numchan=" + str(1) + " " + ""
    )
    osmosdr_sink.set_time_unknown_pps(osmosdr.time_spec_t())
    osmosdr_sink.set_sample_rate(samp_rate)
    osmosdr_sink.set_center_freq(freq, 0)
    osmosdr_sink.set_freq_corr(0, 0)
    osmosdr_sink.set_gain(RF_gain, 0)
    osmosdr_sink.set_if_gain(IF_gain, 0)
    osmosdr_sink.set_bb_gain(20, 0)
    osmosdr_sink.set_antenna('', 0)
    osmosdr_sink.set_bandwidth(sdr_bandwidth, 0)

    tb.connect(source, osmosdr_sink)

    tb.start()
    time.sleep(delay)
    tb.stop()
    tb.wait()

#Gain set through signal power calculation.

def set_gains(power):
    if -40 <= power <= 5:
        RF_gain = 0
        if power < -5:
            IF_gain = power + 40
        elif -5 <= power <= 2:
            IF_gain = power + 41
        elif 2 < power <= 5:
            IF_gain = power + 42
    elif power > 5:
        RF_gain = 14
        IF_gain = power + 34
    else:
        print("invalid Jammer Transmit power")

    return RF_gain, IF_gain

#Main calling previous functions

if __name__ == "__main__":
    
    config_file = open("jaml.yaml")
    options = yaml.load(config_file, Loader=yaml.FullLoader)
    
    power = 13
    freq = options.get("freq")
    t_jamming = options.get("t_jamming")

    jam(freq, power, t_jamming)

else:
        print("invalid jammer selection")
