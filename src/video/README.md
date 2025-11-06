# /src/video
## TepSots packet sniffer

**File:** tepsots.py

**Description:**
Low-level IEEE 802.11 / radiotap sniffer that prints newline-delimited frame summaries. Designed for sniffing. Provides:
 - Radiotap + 802.11 header parsing (rate, channel, RSSI, addresses)
 - CLI filters (interface, src/dst lists, types, length, strength, verbose)
 - Machine-friendly output suitable for piping into decoders or log files
 - Root-check and raw AF_PACKET socket binding

## Shell wrapper for tepsots
**File:** tepsots.sh

**Description:**
Convenience shell wrapper that ensures `python3` is used and forwards arguments to `tepsots.py`.

## H.264 video decoder / pipeline
**File:** video_decoder.py

**Description:**
Watches a sniffer log, reconstructs H.264 NAL fragments, and decodes frames via `ffmpeg` to PNG images. Provides:
 - Inotify-based file watching for appended sniffer logs
 - Buffering of SPS/PPS/keyframe fragments and feeding them to `ffmpeg`
 - PNG output to an image folder for GUI consumption (e.g., `data/images/`)
 - Assumes the sniffer produces hex-encoded payloads in a fixed log format
