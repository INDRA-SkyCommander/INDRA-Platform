# /modules
## Command injector (Tello-focused)
**File:** cmdinjector.py

**Description:**
A UDP MitM / command injector for Tello-style drones. Provides:
 - Sniff-and-forward of UDP command traffic to/from a drone
 - Keyboard-driven command injection (WASD/up/down, takeoff/land)
 - Forging and replaying control packets for live experiments

## Deauthentication helpers
**File:** deauth.py

**Description:**
Helper utilities for deauth and channel-hopping flows. Provides:
 - Channel switching helpers and interface control
 - Deauth frame send wrappers (aireplay/pcap injection hooks)

## Simple GNURadio jammer template
**File:** dumbjammer.py

**Description:**
A template GNURadio flowgraph script that demonstrates basic jamming/noise generation.

## YAML-driven jammer
**File:** Jammer.py

**Description:**
Higher-level jamming orchestrator that reads `jaml.yaml` and runs jamming bursts.

## Jammer configuration file
**File:** jaml.yaml

**Description:**
YAML config consumed by `Jammer.py`. Typical fields:
 - `freq` — center frequency (Hz) for jamming
 - `t_jamming` — burst duration (seconds)
 - `gain` / `sample_rate` / device settings

## Skyjack (module entrypoint)
**File:** skyjack.py

**Description:**
Lightweight skyjacking module intended for integration with the GUI.

## Skyjack (reference/orchestrator)
**File:** skyjackold.py

**Description:**
More complete skyjack orchestrator useful as a reference implementation.

## Video interceptor / pipeline orchestrator
**File:** video_interceptor.py

**Description:**
Glue script that coordinates monitor-mode setup, the sniffer, and the decoder to populate the GUI image sink. Provides:
 - Interface preparation (monitor mode entrypoint)
 - Subprocess control to spawn `tepsots` and `video_decoder` pipelines
 - Writes decoded PNG frames to `data/images/` for GUI consumption
