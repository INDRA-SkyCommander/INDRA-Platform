# /src/video

Small utilities for **authorized, controlled** 802.11 capture + offline decoding workflows (e.g., a lab network you own).
This folder is intentionally focused on **analysis of your own captures**.

## Files

- **`tepsots.py`**: Low-level IEEE 802.11 / radiotap sniffer that prints newline-delimited frame summaries. It includes
  basic filtering options (src/dst/type/len/RSSI) and binds a raw socket (requires elevated privileges).
- **`tepsots.sh`**: Tiny wrapper that runs `tepsots.py` with `python3` when available and forwards CLI args.
- **`video_decoder.py`**: Watches an appended sniffer log, reconstructs H.264 NAL fragments, and uses **FFmpeg** to decode
  frames to PNG files for later viewing/GUI use.

## Data flow (high level)

1. **Sniffer** emits one line per frame (metadata + payload).
2. **Decoder** tails the log file, buffers H.264 fragments, and periodically calls FFmpeg to decode and write images.

## Log format expected by `video_decoder.py`

`video_decoder.py` expects each log line to have **13 space-separated fields**:
`time phy size ft fs src dst sn fn chan rate rssi data`

The final field (`data`) is expected to be a hex-encoded payload string.

## Dependencies

Depending on what you run, you may need:

- Python 3
- Linux raw-socket capture support (sniffer)
- `ffmpeg` on PATH (decoder)
- Python packages used by the decoder: `numpy`, `Pillow`

