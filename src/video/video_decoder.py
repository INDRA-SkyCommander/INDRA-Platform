#!/bin/sh
'''which' python3 > /dev/null && exec python3 "$0" "$@" || exec python "$0" "$@"
'''

#
# Copyright (c) 2018, Manfred Constapel
# This file is licensed under the terms of the MIT license.
#

# 
# Pythonic DJI Ryze Tello Workbench: Example
# 
# Extract h.264 video frames from a captured live stream (video.log)
# and save the h.264 video frames as image files ([seq].png) using FFmpeg.
# 
#  1. read raw video from log file
#  2. pipe raw video data to FFmpeg via stdin
#  3. ffmpeg does the work (decoding and converting)
#  4. FFmpeg pipes output to stdout
#  5. Output from FFmpeg is passed to Pillow
#  6. Pillow creates an image
#  

import json
import time
import sys
import os
import signal
import numpy as np
import subprocess as sp
import PIL.Image as pil
from inotify_simple import INotify, flags

# Global variables for cleanup
i = None
wd = None

def split(value, size=2):
	return tuple(value[0 + i:size + i] for i in range(0, len(value), size))

def hex2dec(value):
	if isinstance(value, str):
		value = value.strip()
		if ' ' not in value:
			return int(value, 16)
		else:
			return hex2dec(value.split(' '))
	else:
		return tuple(int(item, 16) for item in value)

def collect(line):
	line = line.strip().split(' ')
	if len(line) != 13:
		return None
	line, data = line[:-1], line[-1]
	t, phy, size, ft, fs, src, dst, fsn, ffn, chan, rate, rssi = line
	t, size = float(t), int(size)
	ft, fs = int(ft), int(fs)
	src, dst = src if src != str(None) else None, dst if dst != str(None) else None
	fsn, ffn = int(fsn) if fsn != str(None) else None, int(ffn) if ffn != str(None) else None
	chan, rssi = int(chan), int(rssi)
	rate = float(rate) if rate != str(None) else None
	return {'t': t, 'size': size, 'phy': phy, 'ft': ft, 'fs': fs, 'src': src, 'dst': dst, 'sn': fsn, 'fn': ffn, 'chan': chan, 'rate': rate, 'rssi': rssi, 'data': data}

def print_80211(name, sn, fn, size, vs, vf, data):
	vs = vs if vs != -1 else ''
	vf = vf if vf != -1 else ''
	print('{} {:4d} {:1d} {:>3} {:>3} {:4d} {}'.format(name, sn, fn, vs, vf, len(data), data[:10]))

def create_image_ffmpeg(data, fname):

	frame = hex2dec(split(data, 2))
	if os.path.isfile(fname):
		os.remove(fname)

	fmt = 'rgb24'  # rgb24, gray, ya8, rgba
	cmd = ('ffmpeg', '-v', 'warning', '-i', '-', '-f', 'image2pipe', '-pix_fmt', fmt, '-vcodec', 'rawvideo', '-')
	proc = sp.Popen(cmd, bufsize=10**8, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE)        
	
	(out, err) = proc.communicate(np.asarray(frame, dtype='uint8').tobytes())

	w, h = 960, 720  # TODO: extract image size from output of FFmpeg
	nbcomp, bitpix, shape = 0, 0, None
	if fmt == 'gray':
		nbcomp, bitpix, shape = 1, 8, (h, w)
	elif fmt == 'ya8':
		nbcomp, bitpix, shape = 2, 16, (h, w, 2)
	elif fmt == 'rgb24':
		nbcomp, bitpix, shape = 3, 24, (h, w, 3)
	elif fmt == 'rgba':
		nbcomp, bitpix, shape = 4, 32, (h, w, 4)

	if shape is None:
		return

	size = np.prod(shape)
	frame_count = 0
	while len(out) >= size:  # enough data in stream?
		raw_image = out[:size]
		# Ignore this error, it is handled by hard-coding fmt's value
		image = np.frombuffer(raw_image, dtype='uint{}'.format(bitpix // nbcomp))
		image = image.reshape(shape)
		im = pil.fromarray(image)
		im.save(fname)
		fname = fname.replace('.png', '_{}.png'.format(frame_count))
		out = out[size:]
		frame_count += 1

def cleanup_handler(signum, frame):
	print("Stopping video decoder.")
	try:
		if i and wd:
			i.rm_watch(wd)
			print("INotify watch removed.")
	except Exception as e:
		print(f"Error during cleanup {e}")
	finally:
		print("Video decoder stopped.")
		sys.exit(0)

if __name__ == '__main__':

	if len(sys.argv) < 3:
		print("Usage: video_decoder.py <log_file> <image_folder>")
		sys.exit(1)

	frame_count = 0
	log = sys.argv[1]
	image_folder = sys.argv[2]

	signal.signal(signal.SIGINT, cleanup_handler)
	signal.signal(signal.SIGTERM, cleanup_handler)

	# Setting up Inotify
	i = INotify()
	watch_flags = flags.MODIFY

	max_wait = 30
	wait_time = 0

	while not os.path.exists(log) and wait_time < max_wait:
		print(f"Waiting for log file to be created: {log}")
		time.sleep(1)
		wait_time += 1
	
	if not os.path.exists(log):
		print(f"Error: Log file not found at {log} after {max_wait} seconds.")


	try:
		wd = i.add_watch(log, watch_flags)
		print(f"Watching log file: {log}")
	except Exception as e:
		print(f"Error setting up file watch: {e}")
		sys.exit(1)
		
	with open(log, 'r') as file:
		file.seek(0, os.SEEK_END)  # Move the pointer to the end of the file

		sps, pps, key = None, None, None
		buffer = ''

		print("Decoder ready, waiting for data...")

		while True:
			try:
				events = i.read(timeout=1000)
				if not events:
					continue

				for event in events:
					if event is None:
						continue

					for flag in flags.from_mask(event.mask):
						if 'MODIFY' in str(flag):
							while True:
								line = file.readline()
								if not line:
									# break to wait for next event
									break

								r = collect(line)

								if r is not None and r['phy'] in ('g', 'n', 'ac') and r['ft'] == 2:  # streaming
									sn, fn, size, data = r['sn'], r['fn'], r['size'], r['data']

									if fn == 0:  # chunk or first fragment of chunk
										qos, llc, ip, udp = 8 * 3 + 2, 8, 8 * 2 + 4, 8
										data = data[(qos + llc + ip + udp) * 2:]
										vsn, vfn = data[0:2], data[2:4]
										vsn = int(vsn, 16) if len(vsn) > 0 else -1  # app video sn
										vfn = int(vfn, 16) if len(vfn) > 0 else -1  # app video fn
										data = data[4:]  # cut off video app data

									else:  # fragment of chunk
										qos = 8 * 3 + 2
										vsn, vfn = -1, -1
										data = data[qos * 2:]

									data = data[:-8]  # cut off crc

									if '0000000167' == data[:10]:  # SPS
										sps, pps, key, buffer = vsn, None, None, ''
										buffer += data

									if '0000000168' == data[:10] and sps is not None:  # PPS
										if vsn == sps + 1:
											pps = vsn
											buffer += data
										else:
											sps, buffer = None, ''

									if '0000000165' == data[:10] and pps is not None:  # keyframe
										if vsn == pps + 1:
											key = vsn
										else:
											pps, buffer = None, ''

									if key is not None:
										buffer += data

									if fn == 0 and vsn == key and vfn // 128 == 1:  # indicator for last chunk
										sps, pps = None, None

									if sps is None and pps is None and vsn != key:  # last fragment of last chunk
										if len(buffer) > 0:
											create_image_ffmpeg(buffer, os.path.join(image_folder, '{}.png'.format(frame_count)))
											frame_count += 1
										sps, pps, key, buffer = None, None, None, ''

									if '0000000141' == data[:10]:  # for sure, reset (optionally)
										sps, pps, key, buffer = None, None, None, ''
			except KeyboardInterrupt:
				cleanup_handler(None, None)
			except Exception as e:
				print(f"Error in main loop: {e}", file=sys.stderr)
				time.sleep(0.1)				