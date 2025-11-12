#!/bin/sh

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


import time
import sys
import os
import signal
import numpy as np
import subprocess as sp
import PIL.Image as pil

def split(value, size=2):
	"""
	Splits a hex string into a tuple of 2-char strings.
	"""
	return tuple(value[0 + i:size + i] for i in range(0, len(value), size))

def hex2dec(value):
	"""
	Converts a hex string or tuple of hex strings to decimals.
	"""

	if isinstance(value, str):
		value = value.strip()
		if ' ' not in value:
			return int(value, 16)
		else:
			return hex2dec(value.split(' '))
	else:
		return tuple(int(item, 16) for item in value)

def collect(line):
	"""
	Parses a single line from sniff_output_log
	Expecs 13 space-separated columns.
	"""
	line = line.strip().split(' ')
	if len(line) != 13:
		print("Invalid sniff format")
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

def create_image_ffmpeg(data, fname):
	"""
	Uses FFmpeg to decode a raw H.264 and save it as a PNG.
	"""

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
		image = np.frombuffer(raw_image, dtype='uint{}'.format(bitpix // nbcomp))
		image = image.reshape(shape)
		im = pil.fromarray(image)
		im.save(fname)
		fname = fname.replace('.png', '_{}.png'.format(frame_count))
		out = out[size:]
		frame_count += 1

def follow(sniff_file):
	sniff_file.seek(0, os.SEEK_END) # EoF
	while True:
		line = sniff_file.readline()
		if not line:
			time.sleep(0.1)
			continue
		yield line

def cleanup_handler(signum, frame):
	"""
	Exits gracefully.
	"""

	print("Stopping video decoder.")
	sys.exit(0)

def extract_image(line, frame_count):
	r = collect(line)

	if r is None:
		print("None recieved!")
		return None

	if r is not None and r['phy'] in ('g', 'n', 'ac') and r['ft'] == 2:  # streaming
		sn, fn, size, data = r['sn'], r['fn'], r['size'], r['data']
		
		if fn == 0:  # chunk or first fragment of chunk
			vsn, vfn = data[0:2], data[2:4]
			vsn = int(vsn, 16) if len(vsn) > 0 else -1  # app video sn
			vfn = int(vfn, 16) if len(vfn) > 0 else -1  # app video fn
			data = data[4:]  # cut off video app data

		else:  # fragment of chunk
			vsn, vfn = -1, -1

		data = data[:-8]  # cut off crc

		# Check for reset packet
		if '0000000141' == data[:10]:  # for sure, reset (optionally)
			print("DEBUG: Found 041 reset packet.")
			sps, pps, key, buffer = None, None, None, ''
			return None

		# Check for SPS
		if '0000000167' == data[:10]:  # SPS
			print("DEBUG: Found SPS packet.")
			sps, pps, key, buffer = vsn, None, None, ''
			buffer += data

		# Check for PPS
		if '0000000168' == data[:10] and sps is not None:  # PPS
			# vsn is not incrementing
			if vsn >= sps:
				print("DEBUG: Found PPS packet.")
				pps = vsn
				buffer += data
			else:
				print("DEBUG: Found PPS packet, but SN mismatch.")
				sps, buffer = None, ''

		# Check for Keyframe
		if '0000000165' == data[:10] and pps is not None:  # keyframe
			if vsn >= pps:
				print("DEBUG: Found Keyframe packet.")
				key = vsn
			else:
				print("DEBUG: Found PPS packet, but SN mismatch.")
				pps, buffer = None, ''

		# Collect frame data if we have key
		if key is not None:
			buffer += data

		# Check for end of frame
		if fn == 0 and vsn == key and vfn // 128 == 1:  # indicator for last chunk
			print("DEBUG: Found EOF.")
			sps, pps = None, None

		if sps is None and pps is None and vsn != key:  # last fragment of last chunk
			if len(buffer) > 0:
				print("DEBUG: CALLING FFMPEG.")
				create_image_ffmpeg(buffer, os.path.join(image_folder, '{}.png'.format(frame_count)))
				return 1

if __name__ == '__main__':

	if len(sys.argv) < 3:
		print("Usage: video_decoder.py <log_file> <image_folder>")
		sys.exit(1)

	frame_count = 0
	log = sys.argv[1]
	image_folder = sys.argv[2]

	signal.signal(signal.SIGINT, cleanup_handler)
	signal.signal(signal.SIGTERM, cleanup_handler)

	max_wait = 30
	wait_time = 0

	print(f"Waiting for log file to be created: {log}")
	while not os.path.exists(log) and wait_time < max_wait:
		time.sleep(1)
		wait_time += 1
	
	if not os.path.exists(log):
		print(f"Error: Log file not found at {log} after {max_wait} seconds.")

	print(f"Watching log file: {log}")
	
	sps, pps, key = None, None, None
	buffer = ''

	print("Decoder ready, waiting for data...")

	frame_count = 0
	logfile = open(log)
	loglines = follow(logfile)

	for line in loglines:
		# pass to image handler
		image = extract_image(line, frame_count)
		if (image == 1):
			print("image saved!")
		else:
			print("SN mismatch!")
