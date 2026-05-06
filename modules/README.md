# Modules

These scripts are intended for **authorized** research, lab demos, and defensive testing **only**.  
Only run them on hardware and networks you own or have explicit permission to test.

## What's in this folder

- **deauth/** — Wireless deauthentication test helper used in controlled environments. Reads target/interface options from `data/module_input_data.json`.
- **gps_spoof_dynamic/** — GPS L1 spoofing module that supports both static mode (`-l`) and trajectory mode (`-u` or `-x`) from a user-selected CSV (same style as `circle.csv`, `rocket.csv`, `satellite.csv`, `circle_llh.csv`), then transmits via HackRF. Uses the in-repo `gps-sdr-sim/` folder.
- **gps_spoof/** — Shared GUI support files used by `gps_spoof_dynamic`.

## Setup for GPS spoof module

The GPS module depends on tools and data under `gps-sdr-sim/` (now included in this repository).

1. Install Python dependencies from repo root:
  - `pip3 install -r requirements.txt`
2. Install system tools:
  - `gcc`, `make` (to build `gps-sdr-sim`)
  - `hackrf_transfer` (HackRF host tools)
3. Build gps-sdr-sim binary:
  - `cd gps-sdr-sim && make`
4. Return to repo root and start INDRA:
  - `cd .. && ./INDRA-Start.sh`

## Configuration

All modules expect a JSON file at:

- `data/module_input_data.json`

At a minimum, it should include target metadata and options (example shape):

```json
{
  "target_name": "Example",
  "target_info": { "mac_address": "xx:xx:xx:xx:xx:xx", "channel": 1 },
  "options": { "interface": "wlan0", "packets": 30 }
}
```

The **gps_spoof_dynamic** module adds:

```json
{
  "gps_spoof_dynamic": {
    "latitude": "40.7128",
    "longitude": "-74.0060",
    "altitude": "100",
    "csv_file": "/home/user/path/to/trajectory.csv",
    "tx_power": "0"
  }
}
```

Notes:
- If `csv_file` is provided, trajectory mode is used.
- If `csv_file` is empty, static mode uses `latitude`, `longitude`, and `altitude`.

NASA Earthdata credentials for ephemeris downloads can be provided via the
`NASA_USER` and `NASA_PASS` environment variables.

## Safety notes

Wireless testing can disrupt nearby devices. GPS spoofing is illegal in most
jurisdictions. Use a shielded environment or approved lab space, and follow
your organization's policies.
