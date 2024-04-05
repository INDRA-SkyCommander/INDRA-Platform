#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Mpsk Stage1
# GNU Radio version: 3.10.9.2

from PyQt5 import Qt
import sys 
print(sys.version)
#from gnuradio import qtgui
import gnuradio
from gnuradio import analog
from gnuradio import blocks
from gnuradio import filter
from gnuradio.filter import firdes
from gnuradio import gr
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
import osmosdr
import time



class mpsk_stage1(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "Mpsk Stage1", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Mpsk Stage1")
        #qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except BaseException as exc:
            print(f"Qt GUI: Could not set Icon: {str(exc)}", file=sys.stderr)
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("GNU Radio", "mpsk_stage1")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)

        ##################################################
        # Variables
        ##################################################
        self.variable_channel_size = variable_channel_size = 20
        self.sps = sps = 4
        self.excess_bw = excess_bw = 2.6*variable_channel_size/10
        self.samp_rate = samp_rate = 20e6
        self.rrc_taps = rrc_taps = firdes.root_raised_cosine(1, sps, 1, excess_bw, 45)
        self.center_frequency = center_frequency = 2437e6

        ##################################################
        # Blocks
        ##################################################

        self.osmosdr_sink_0 = osmosdr.sink(
            args="numchan=" + str(1) + " " + ''
        )
        self.osmosdr_sink_0.set_time_unknown_pps(osmosdr.time_spec_t())
        self.osmosdr_sink_0.set_sample_rate(samp_rate)
        self.osmosdr_sink_0.set_center_freq(center_frequency, 0)
        self.osmosdr_sink_0.set_freq_corr(0, 0)
        self.osmosdr_sink_0.set_gain(20, 0)
        self.osmosdr_sink_0.set_if_gain(20, 0)
        self.osmosdr_sink_0.set_bb_gain(20, 0)
        self.osmosdr_sink_0.set_antenna('', 0)
        self.osmosdr_sink_0.set_bandwidth(0, 0)
        self.fir_filter_xxx_0_0_0_0_0 = filter.fir_filter_ccc(1, rrc_taps)
        self.fir_filter_xxx_0_0_0_0_0.declare_sample_delay(0)
        self.blocks_throttle_0_0 = blocks.throttle(gr.sizeof_gr_complex*1, samp_rate,True)
        self.blocks_add_xx_0 = blocks.add_vcc(1)
        self.band_pass_filter_0 = filter.fir_filter_ccf(
            1,
            firdes.band_pass(
                1,
                samp_rate,
                1,
                (variable_channel_size*1e6/2),
                100e3,
                window.WIN_HAMMING,
                6.76))
        self.analog_sig_source_x_0_1_0 = analog.sig_source_c(samp_rate, analog.GR_COS_WAVE, (samp_rate+((.7*variable_channel_size*1e6)/2)), .025, 0, 0)
        self.analog_sig_source_x_0_1 = analog.sig_source_c(samp_rate, analog.GR_COS_WAVE, (samp_rate-((.7*variable_channel_size*1e6)/2)), (-.023), 0, 0)
        self.analog_sig_source_x_0_0 = analog.sig_source_c(samp_rate, analog.GR_COS_WAVE, (samp_rate+((.9*variable_channel_size*1e6)/2)), .02, 0, 0)
        self.analog_sig_source_x_0 = analog.sig_source_c(samp_rate, analog.GR_COS_WAVE, (samp_rate-((.9*variable_channel_size*1e6)/2)), .02, 0, 0)
        self.analog_noise_source_x_0 = analog.noise_source_c(analog.GR_UNIFORM, 1, 0)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.analog_noise_source_x_0, 0), (self.blocks_throttle_0_0, 0))
        self.connect((self.analog_sig_source_x_0, 0), (self.blocks_add_xx_0, 1))
        self.connect((self.analog_sig_source_x_0_0, 0), (self.blocks_add_xx_0, 4))
        self.connect((self.analog_sig_source_x_0_1, 0), (self.blocks_add_xx_0, 2))
        self.connect((self.analog_sig_source_x_0_1_0, 0), (self.blocks_add_xx_0, 3))
        self.connect((self.band_pass_filter_0, 0), (self.blocks_add_xx_0, 0))
        self.connect((self.blocks_add_xx_0, 0), (self.osmosdr_sink_0, 0))
        self.connect((self.blocks_throttle_0_0, 0), (self.fir_filter_xxx_0_0_0_0_0, 0))
        self.connect((self.fir_filter_xxx_0_0_0_0_0, 0), (self.band_pass_filter_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "mpsk_stage1")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_variable_channel_size(self):
        return self.variable_channel_size

    def set_variable_channel_size(self, variable_channel_size):
        self.variable_channel_size = variable_channel_size
        self.set_excess_bw(2.6*self.variable_channel_size/10)
        self.analog_sig_source_x_0.set_frequency((self.samp_rate-((.9*self.variable_channel_size*1e6)/2)))
        self.analog_sig_source_x_0_0.set_frequency((self.samp_rate+((.9*self.variable_channel_size*1e6)/2)))
        self.analog_sig_source_x_0_1.set_frequency((self.samp_rate-((.7*self.variable_channel_size*1e6)/2)))
        self.analog_sig_source_x_0_1_0.set_frequency((self.samp_rate+((.7*self.variable_channel_size*1e6)/2)))
        self.band_pass_filter_0.set_taps(firdes.band_pass(1, self.samp_rate, 1, (self.variable_channel_size*1e6/2), 100e3, window.WIN_HAMMING, 6.76))

    def get_sps(self):
        return self.sps

    def set_sps(self, sps):
        self.sps = sps
        self.set_rrc_taps(firdes.root_raised_cosine(1, self.sps, 1, self.excess_bw, 45))

    def get_excess_bw(self):
        return self.excess_bw

    def set_excess_bw(self, excess_bw):
        self.excess_bw = excess_bw
        self.set_rrc_taps(firdes.root_raised_cosine(1, self.sps, 1, self.excess_bw, 45))

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.analog_sig_source_x_0.set_sampling_freq(self.samp_rate)
        self.analog_sig_source_x_0.set_frequency((self.samp_rate-((.9*self.variable_channel_size*1e6)/2)))
        self.analog_sig_source_x_0_0.set_sampling_freq(self.samp_rate)
        self.analog_sig_source_x_0_0.set_frequency((self.samp_rate+((.9*self.variable_channel_size*1e6)/2)))
        self.analog_sig_source_x_0_1.set_sampling_freq(self.samp_rate)
        self.analog_sig_source_x_0_1.set_frequency((self.samp_rate-((.7*self.variable_channel_size*1e6)/2)))
        self.analog_sig_source_x_0_1_0.set_sampling_freq(self.samp_rate)
        self.analog_sig_source_x_0_1_0.set_frequency((self.samp_rate+((.7*self.variable_channel_size*1e6)/2)))
        self.band_pass_filter_0.set_taps(firdes.band_pass(1, self.samp_rate, 1, (self.variable_channel_size*1e6/2), 100e3, window.WIN_HAMMING, 6.76))
        self.blocks_throttle_0_0.set_sample_rate(self.samp_rate)
        self.osmosdr_sink_0.set_sample_rate(self.samp_rate)

    def get_rrc_taps(self):
        return self.rrc_taps

    def set_rrc_taps(self, rrc_taps):
        self.rrc_taps = rrc_taps
        self.fir_filter_xxx_0_0_0_0_0.set_taps(self.rrc_taps)

    def get_center_frequency(self):
        return self.center_frequency

    def set_center_frequency(self, center_frequency):
        self.center_frequency = center_frequency
        self.osmosdr_sink_0.set_center_freq(self.center_frequency, 0)




def main(top_block_cls=mpsk_stage1, options=None):

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()

    #tb.show()  # Is this spawning the empty GUI and doing nothing else?

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
