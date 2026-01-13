#!/usr/bin/env python3

import os
import time
import yaml
import sys
import osmosdr
from gnuradio import gr
from gnuradio import analog

#=====
#Ignore 'no attribute' errors, fault on Pylint's side not code
#=====

def jam(freq, power, samp_rate, sdr_bandwidth, delay=1.0):
    """
    Configures and runs the GNU radio flowgraph to transmit noise
    """

    print(f"\nJamming frequency: {freq / 1e6} MHz")
    print(f"Sample Rate: {samp_rate / 1e6} Mhz")
    print(f"Bandwidth: {sdr_bandwidth / 1e6} MHz")
    print(f"Jamming for: {delay} second(s)")

    try:
        RF_gain, IF_gain = set_gains(power) # HackRF SDR antenna gain
        print(f"Power: {power} dB | RF Gain: {RF_gain} | IF Gain: {IF_gain}")
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    tb = gr.top_block()

    # Guassian noise
    
    source = analog.noise_source_c(analog.GR_GAUSSIAN, 1, 1)

    #HackRF parameters are set below. These are specific to the hackrf and are set with osmosdr.sink
    #all other supplied values are tuned for the device.
    
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

    print("Jamming started.")
    tb.start()
    try:
        time.sleep(delay)
    except KeyboardInterrupt:
        print("Jamming interrupted by user.")
    tb.stop()
    tb.wait()
    print("Jamming complete.")

# Gain set through signal power calculation.

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
        raise ValueError(f"Invalid jammer transmit power: {power} dB. Must be -40 to 5")

    return RF_gain, IF_gain

# Main calling previous functions

if __name__ == "__main__":
    
    jammer_prefs = os.path.join(os.path.dirname(__file__), "jaml.yaml")

    try:
        config_file = open(jammer_prefs)
    except FileNotFoundError:
        print("Error: 'jaml.yaml' configuration file not found.")
        sys.exit(1)

    options = yaml.load(config_file, Loader=yaml.FullLoader)
    
    power_str = options.get("power")
    freq_str = options.get("freq")
    samp_rate_str = options.get("samp_rate")
    sdr_bandwidth_str = options.get("sdr_bandwidth")
    t_jamming_str = options.get("t_jamming")

    if not all([power_str, freq_str, t_jamming_str, samp_rate_str, sdr_bandwidth_str]):
        print("Error: 'jaml.yaml' is missing one or more required keys.")
        sys.exit(1)

    try:
        power = float(power_str)
        freq = float(freq_str)
        t_jamming = float(t_jamming_str)
        samp_rate = float(samp_rate_str)
        sdr_bandwidth = float(sdr_bandwidth_str)
    except ValueError as e:
        print(f"Error: Invalid non-numeric value in 'jaml.yaml' {e}")
        sys.exit(1)

    jam(freq, power, samp_rate, sdr_bandwidth, delay=t_jamming)
else:
    print("invalid jammer selection")
