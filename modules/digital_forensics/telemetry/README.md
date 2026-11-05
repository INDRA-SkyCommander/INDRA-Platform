# telemetry

Python port of the DroneXtract `telemetry` package, extended with a **USB forensic scanner**. Plug a DJI drone's SD card in and the scanner extracts all DJI files into a timestamped folder.

---

> **Must install dependencies before use:**
> ```bash
> pip install colorama python-dotenv staticmap plotext Pillow psutil
> ```

---

## Files

| File | Description |
|------|-------------|
| `scanner.py` | USB drive detection and extraction engine |
| `telemetry.py` | `DJIFlightPathMap` and `DJITelemetryVisualizations` classes + `execute_telemetry` dispatcher |

---

## Dependencies

```bash
pip install colorama python-dotenv staticmap plotext Pillow psutil
```

| Package | Purpose |
|---------|---------|
| `colorama` | Terminal color output |
| `python-dotenv` | `.env` file loading for downsample config |
| `staticmap` | Static PNG map rendering via OSM tiles |
| `plotext` | ASCII terminal charts |
| `Pillow` | Image I/O (required by `staticmap`, also used for EXIF extraction) |
| `psutil` | USB drive detection and cross-process drive listing |

---

## Configuration (`.env`)

Place these in the project root `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `FLIGHT_MAP_DOWNSAMPLE` | `100` | Max coordinates before downsampling for the flight map |
| `TELEMETRY_VIS_DOWNSAMPLE` | `200` | Max data points before downsampling for the ASCII chart |

---

## What Gets Extracted

When you click **Scan Drone**, the scanner:

1. Walks the entire drive recursively
2. Copies all DJI files to `<output>/forensic_<timestamp>/raw_files/`
3. Runs extractions into `<output>/forensic_<timestamp>/extracted/`
4. Writes a `report.json` summary

### File types handled

| Extension | Type | Extraction |
|-----------|------|-----------|
| `.csv` | CSV Flight Record | If it has `latitude`/`longitude` columns → generates a PNG flight path map |
| `.jpg` / `.jpeg` | JPEG Image | EXIF metadata extracted to a `.json` file per image |
| `.dng` | DNG Raw Image | Copied; note to use `exiftool` for full metadata |
| `.srt` | DJI Subtitle | Copied; contains per-frame telemetry (GPS, altitude, speed) — use `parsing` to decode |
| `.txt` | TXT Flight Log | Copied |
| `.dat` | Internal Log | Copied; requires DatCon or `dji-log-parser` for binary decoding |
| `.gpx` | GPX Track | Copied — use `parsing` to parse |
| `.kml` | KML Track | Copied — use `parsing` to parse |
| `.mp4` / `.mov` | Video | Copied |

### Output folder structure

```
DroneXtract_Output/
└── forensic_20241015_143022/
    ├── raw_files/          ← all discovered files copied here
    │   ├── DJI_0001.jpg
    │   ├── MAVIC3.srt
    │   └── ...
    ├── extracted/
    │   ├── flight_map.png  ← generated from CSV lat/lon data
    │   ├── DJI_0001_exif.json
    │   └── ...
    └── report.json         ← full summary of everything found and extracted
```

---

## Internal Storage vs. SD Card

DJI drones plugged in via USB normally expose only the **SD card** as a removable drive. Internal storage (`.DAT` flight logs) is only accessible if:
- The drone mounts its internal storage as a second drive (model-dependent), or
- You use **DJI Assistant 2**, which uses a proprietary USB protocol

If internal logs are present, the scanner copies them and notes them in the report. Decoding requires [DatCon](https://datfile.net/) (Java) or [dji-log-parser](https://github.com/o-gs/dji-firmware-tools).

---

## Telemetry Tools (standalone)

The `telemetry.py` module can also be used independently without a drone connection — give it a pre-exported CSV file.

### Dispatcher

```python
from telemetry import execute_telemetry

execute_telemetry(1)  # Flight Path Map — prompts for CSV + output PNG path
execute_telemetry(2)  # Telemetry Visualizations — prompts for CSV, then shows channel menu
```

### Individual classes

```python
from telemetry import DJIFlightPathMap, DJITelemetryVisualizations

DJIFlightPathMap("flight.csv", "map.png").execute_flight_path_analysis()
DJITelemetryVisualizations("flight.csv").execute_telemetry_visualizations()
```

### CLI

```bash
python telemetry.py
```

---

## Supported Telemetry Channels (1–45)

| # | Channel | # | Channel |
|---|---------|---|---------|
| 1 | Height Above Takeoff (feet) | 24 | RC Aileron |
| 2 | Height Above Ground (feet) | 25 | RC Throttle |
| 3 | Ground Elevation (feet) | 26 | RC Rudder |
| 4 | Ground Elevation (feet) | 27 | RC Elevator (percent) |
| 5 | Altitude Above Sea Level (feet) | 28 | RC Aileron (percent) |
| 6 | Height Sonar (feet) | 29 | RC Throttle (percent) |
| 7 | Speed (mph) | 30 | RC Rudder (percent) |
| 8 | Distance (feet) | 31 | Gimbal Heading (degrees) |
| 9 | Mileage (feet) | 32 | Gimbal Pitch (degrees) |
| 10 | Satellites | 33 | Gimbal Roll (degrees) |
| 11 | GPS Level | 34 | Battery Percent |
| 12 | Voltage (V) | 35 | Voltage Cell 1 |
| 13 | Max Altitude (feet) | 36 | Voltage Cell 2 |
| 14 | Max Ascent (feet) | 37 | Voltage Cell 3 |
| 15 | Max Speed (mph) | 38 | Voltage Cell 4 |
| 16 | Max Distance (feet) | 39 | Voltage Cell 5 |
| 17 | X Speed (mph) | 40 | Voltage Cell 6 |
| 18 | Y Speed (mph) | 41 | Current (A) |
| 19 | Z Speed (mph) | 42 | Battery Temperature (F) |
| 20 | Compass Heading (degrees) | 43 | Altitude (feet) |
| 21 | Pitch (degrees) | 44 | Ascent (feet) |
| 22 | Roll (degrees) | 45 | Flyc State Raw |
| 23 | RC Elevator | | |

---

## Virtual Environment (recommended)

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
python gui.py
```
