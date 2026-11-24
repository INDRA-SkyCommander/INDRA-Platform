# digital_forensics

INDRA's drone forensics module. It takes the files copied off a DJI drone or its SD card, decodes the flight data, extracts photo and video metadata, screens images for hidden data, and draws maps of where the drone flew. The **Forensics** tab of the INDRA GUI (`src/gui/IndraGUI.py`) runs everything here. You can also call each part from Python or the command line.

The `parsing/` and `telemetry/` packages started as a Python port of [DroneXtract](https://github.com/ANG13T/DroneXtract) (Go). `analysis/` and the `.DAT` decoder were written for INDRA.

---

## Contents

- [Quick start](#quick-start)
- [How the pieces fit](#how-the-pieces-fit)
- [Folder layout](#folder-layout)
- [GUI cards and the code behind them](#gui-cards-and-the-code-behind-them)
- [analysis/: per-session analyzers](#analysis-per-session-analyzers)
- [parsing/: file decoders](#parsing-file-decoders)
- [telemetry/: SD card scanner and maps](#telemetry-sd-card-scanner-and-maps)
- [drone_pipeline/: command-line entry point](#drone_pipeline-command-line-entry-point)
- [Output files](#output-files)
- [Dependencies and configuration](#dependencies-and-configuration)
- [Known limitations](#known-limitations)

---

## Quick start

From the **repo root** (`INDRA-Platform/`). The analyzers import as `modules.digital_forensics...`, so the repo root has to be your working directory.

```bash
pip install Pillow psutil matplotlib colorama gpxpy plotext python-dotenv
```

**Using the GUI:** start INDRA, open the **Forensics** tab, and either:

- run an **extraction** (hashed, chain-of-custody copy) and then click **Parse Logs**, **Extract Metadata**, **Scan Images** or **Generate Map**, or
- plug in a card and click **Scan SD Card** for a quick, unhashed look.

**Without the GUI:**

```bash
# Scan an SD card: copy DJI files, decode .DAT logs, write report.json
python3 modules/digital_forensics/drone_pipeline/main.py scan --output-dir data/extracted

# Build media-telemetry CSVs for an existing extraction session
python3 -m modules.digital_forensics.analysis.media_telemetry data/extracted/<session>/manifest.json

# Decode one .DAT flight log to CSV
python3 -c "import sys; sys.path.insert(0,'modules/digital_forensics/parsing'); \
from dat_parser import parse_dat; print(parse_dat('FLY001.DAT','FLY001_dat.csv'))"
```

---

## How the pieces fit

Evidence enters this module in one of two ways:

```
 ┌───────────────────────────┐            ┌──────────────────────────────┐
 │ Extraction (hashed)       │            │ SD Card Scan (quick look)    │
 │ forensics/acquisition/    │            │ telemetry/scanner.py         │
 │   usb_extractor.py        │            │   scan_drive()               │
 └─────────────┬─────────────┘            └──────────────┬───────────────┘
               │ writes                                  │ writes
               ▼                                         ▼
   <session>/manifest.json                   forensic_<timestamp>/
   (every file: path, category,                raw_files/   extracted/
    sha256, size)                              report.json
               │                                         │
               ▼                                         │
 ┌─────────────────────────────────────┐                 │
 │ analysis/  (each takes manifest.json)│                 │
 │  flight_logs ──► parsing/dat_parser  │◄── View CSV ────┘
 │               ──► parsing/parsers    │   (manifest_from_folder
 │  media_telemetry (photo/video/IDX)   │    builds a stand-in
 │  media_metadata  (EXIF)              │    manifest for the scan)
 │  steganography   (appended data)     │
 │  telemetry       (PNG maps)          │
 └─────────────────────────────────────┘
               │
               ▼
   *_dat.csv, media_telemetry_<date>.csv, *_flight_map.png,
   flight_logs_parsed.txt  →  GUI cards, View CSV, report
```

- **Extraction** (owned by `forensics/acquisition/`, outside this folder) hashes every file and writes `manifest.json`. Each analyzer in `analysis/` takes that manifest's path and picks the files it needs by `category` (`flight_logs`, `media` or `other`).
- **SD Card Scan** (`telemetry/scanner.py`) is faster and does **not** hash anything. It copies DJI file types, decodes `.DAT` logs and writes `report.json`. Use it for triage, not as evidence.

---

## Folder layout

| Path | What it does |
|------|--------------|
| `analysis/__init__.py` | `load_manifest()`, `files_in_category()`, and re-exports the five `analyze_*` functions |
| `analysis/flight_logs.py` | Sorts real DJI flight logs from look-alikes and decodes them (`.DAT`, `.TXT`, `.CSV`, `.KML`, `.GPX`) |
| `analysis/media_telemetry.py` | Pulls GPS, altitude, speed and attitude from photos, videos and `MISC/IDX` files into per-day CSVs. Also produces the **Card Findings** |
| `analysis/media_metadata.py` | EXIF per image: camera, timestamp, GPS with a Google Maps link |
| `analysis/steganography.py` | Flags images with data after the end marker or embedded ZIP/RAR/PDF/7z/GZIP signatures |
| `analysis/telemetry.py` | Draws a PNG map for every CSV in a session that has `latitude`/`longitude` |
| `parsing/dat_parser.py` | Decodes Phantom 3 binary `.DAT` flight logs into CSV and summarises a flight |
| `parsing/dat_display.py` | Labels, units, help text and red/amber alert rules for the **View CSV** window |
| `parsing/parsers.py`, `parsing/helpers.py` | DroneXtract CSV / KML / GPX parsers (terminal tables) and their shared formatting helpers |
| `telemetry/scanner.py` | Finds removable drives (Linux) and runs the SD Card Scan |
| `telemetry/telemetry.py` | DroneXtract flight-path map (OpenStreetMap tiles) and 45-channel ASCII charts |
| `drone_pipeline/main.py` | CLI: `scan` an SD card or `run` one file |

---

## GUI cards and the code behind them

| Forensics-tab card | Button | Calls |
|--------------------|--------|-------|
| Flight Logs / Telemetry | Parse Logs | `analysis.analyze_flight_logs` |
| | View CSV | `dat_parser.parse_dat` (for any `.DAT` not yet decoded), `dat_parser.summarize_dat_rows`, `media_telemetry.summarize_media_rows`, `media_telemetry.card_findings`, `dat_display.*` |
| Media Metadata | Extract Metadata | `analysis.analyze_media` (+ `analyze_media_telemetry`) |
| Steganography | Scan Images | `analysis.analyze_stego` |
| Telemetry — Flight Path Map | Generate Map | `analysis.analyze_telemetry` → `render_flight_map` |
| SD Card Scan | Scan SD Card | `telemetry/scanner.get_usb_drives`, `scan_drive` |
| Reporting | (report section) | `media_telemetry.card_findings` |

Every analysis card takes a session ID. Leave it blank to use the most recent session.

---

## analysis/: per-session analyzers

Every function takes the path to a session's `manifest.json` and returns a plain `dict`. None of them change the copied evidence. They only write new files into the session folder.

```python
from modules.digital_forensics.analysis import (
    analyze_flight_logs, analyze_media, analyze_stego,
    analyze_telemetry, analyze_media_telemetry,
)
result = analyze_flight_logs("data/extracted/<session>/manifest.json")
```

### `analyze_flight_logs(manifest_path)`

The extractor puts every `.dat` and `.txt` file in `flight_logs` based on the extension alone, so this function checks each file before decoding it:

| File | Treated as a flight log when… | What happens |
|------|-------------------------------|--------------|
| `.dat` | `BUILD` at byte 16, or named `FLY###.DAT` | Decoded by `dat_parser` → `<name>_dat.csv` next to the `.dat` |
| `.txt` | Named `DJIFlightRecord*` | Line count, first 15 lines, format guess (not decoded yet) |
| `.csv` / `.kml` / `.gpx` | Always | DroneXtract parser output captured as text |
| anything else | — | `status: "skipped"` with a reason (e.g. *"Windows system file, not a DJI log"*) |

Returns `log_count`, `files_checked`, `skipped_count`, `items` (one per file), `media_telemetry` (see below), and `output_file` (`flight_logs_parsed.txt`, all parser output combined).

### `analyze_media_telemetry(manifest_path, out_dir=None, manifest=None)`

A camera SD card usually has no flight logs, but every photo and video records where the drone was when it was taken. This function collects those snapshots:

| Source | Fields read |
|--------|-------------|
| Photos (`.jpg` `.jpeg` `.dng`) | EXIF `DateTimeOriginal` + GPS; DJI XMP: absolute/relative altitude, X/Y/Z speed, aircraft and gimbal pitch/roll/yaw |
| Videos (`.mov` `.mp4`) | `moov/mvhd` creation time and duration; DJI `udta` atoms: ISO-6709 GPS, speeds, aircraft and gimbal attitude (at the start of the recording) |
| `MISC/IDX/idx##` | Original card path, date, and a copy of the video header. **These can outlive a deleted video.** |

Rows are sorted by time and split into capture sessions. A new session starts after a gap of more than **2 hours** or **5 km**. Each session becomes `media_telemetry_<YYYY-MM-DD>.csv` (23 columns including `sha256` and `time_source`). Files that could not be read are listed in `media_telemetry_info.json`. Running it again deletes the previous CSVs and maps first.

Timestamps are kept exactly as the camera wrote them, and `time_source` says which clock each one came from. No time zone is assumed.

Related helpers:

- `media_telemetry_for_session(manifest_path)`: reuses existing CSVs and only builds them if there are none.
- `manifest_from_folder(folder)`: makes a minimal manifest for an SD Card Scan's `raw_files/`, which has no `manifest.json`.
- `summarize_media_rows(rows, card_files, skipped)`: summary for one CSV (time span, centre point and spread, max altitude and speed, camera models, flags).
- `card_findings(card_files, rows, skipped)`: the **Card Findings** list. Each entry is `{finding, files, why}`:

| Finding | Why it matters |
|---------|----------------|
| Photo or video not named `DJI_####` | Probably renamed after capture |
| Gap in the `DJI_####` numbering | A file was deleted or renamed |
| Files in `DCIM` the camera did not make | Someone added them (calls out `steghide` by name) |
| Index lists a video that is not on the card | Video deleted or moved after recording |
| File could not be read | Damaged or cut short |

### `analyze_media(manifest_path)`

EXIF for each image in the `media` category, read with Pillow: format, dimensions, make, model, `DateTime`, software, and GPS as decimal degrees with a Google Maps link. Video container metadata is not read here; `analyze_media_telemetry` covers that.

### `analyze_stego(manifest_path)`

A quick first check that needs only the standard library. For each image it reports:

1. bytes appended after the JPEG `FFD9` / PNG `IEND` end marker, and
2. ZIP, RAR, PDF, 7z or GZIP signatures found inside the image bytes.

It flags images to look at more closely. It does **not** find LSB stego (e.g. steghide); use dedicated tools for that.

### `analyze_telemetry(manifest_path)`

Finds every CSV in the session that has `latitude` and `longitude` (decoded `_dat.csv` files and media-telemetry CSVs) and writes `<stem>_flight_map.png` for each. `render_flight_map(csv_path, out_path)` draws one map:

- **Offline by default** (matplotlib). The axes show metres east/north of the first point. `.DAT` logs are drawn as a path with start, end and home. Media telemetry is drawn as numbered capture points with no connecting line, because they are snapshots, not a track.
- **Online** (OpenStreetMap tiles via `staticmap`) only when `INDRA_ONLINE_MAPS=1`. This is off by default because downloading tiles **sends the evidence coordinates to a third party**.

---

## parsing/: file decoders

### `dat_parser.py`: Phantom 3 `.DAT` flight logs

```python
from dat_parser import parse_dat, summarize_dat_rows
result = parse_dat("FLY001.DAT", "FLY001_dat.csv")
# {"records_total", "records_parsed", "checksum_errors", "header_skip",
#  "row_count", "csv_path", ["error"]}
```

File format (worked out from the DROP and DatCon sources):

```
[128-byte header, "BUILD" at bytes 16-20]
then repeated records:
[0x55][pktlen u8][0x00][type u8][subtype u8][msg u8][tickNo u32-LE][payload ...]
payload is XOR-decoded with (tickNo % 256); next record starts at pos + pktlen
```

| `rec_type` | type/subtype | Columns |
|------------|--------------|---------|
| `GPS` | `0xCF/0x01` | latitude, longitude, altitude, velocities, satellites, attitude (from quaternion) |
| `FSTAT` | `0x2A/0x0C` | position, height, attitude, `flyc_state` (flight mode), RC connection, failure and GPS-error codes, flight time |
| `HOME` | `0xC6/0x0D` | home point |
| `RC` | `0x98/0x00` | aileron, elevator, throttle, rudder stick positions |
| `BATTERY` | `0x44/0x11` | percent, volts, amps, remaining mAh, temperature, cell 1–4 voltages |

Every row also has `time_s` (seconds since the first decoded record, at 600 ticks/s) and the raw `tick`. `checksum_errors` counts bytes skipped while looking for the next valid record. A high number means the file is damaged or not Phantom 3 format.

`summarize_dat_rows(rows)` returns flight time, max altitude and speed, distance flown, furthest distance from home, battery start/end/min voltage/max temperature, satellite range, how many records show RC signal lost or a failure code, and the flight modes in the order they first appear.

### `dat_display.py`: View CSV presentation

Display only. It never changes the CSV. It holds the flight-mode and GPS-status code tables, column labels and one-line help text, number formatting, and the alert rules used to colour rows:

- **Red:** RC signal lost, failure code, battery under 20% or at 60 °C or above
- **Amber:** weak GPS (under 6 satellites), automatic return or landing mode, GPS error, battery under 30%

### `parsers.py` / `helpers.py`

DroneXtract CSV, KML and GPX parsers. Each prints its results as a box-drawn table in the terminal. A file with the wrong extension prints an error and is skipped.

```python
from parsers import DJI_CSV_Parser, DJI_KML_Parser, DJI_GPX_Parser
DJI_CSV_Parser("flight.csv").parse_contents()
DJI_KML_Parser("flight.kml").parse_contents()
DJI_GPX_Parser("flight.gpx").parse_contents()
```

| Parser | Prints |
|--------|--------|
| CSV | Every row, with column names as labels (any Airdata-style CSV) |
| KML | Home point (coordinates, altitude) from `<Point>` placemarks, then each numbered `<LineString>` coordinate. Works with or without the KML namespace |
| GPX | 2D/3D track length, moving and stopped time, max speed, total climb and descent, start and end times, point count and average spacing |

`helpers.py` holds the colour constants, table-drawing functions, input prompts and file-extension check that the parsers and `telemetry.py` share.

---

## telemetry/: SD card scanner and maps

`scanner.py`:

- `get_usb_drives()`: mount points of removable drives, found through psutil and `/sys/block/<dev>/removable` (**Linux only**).
- `watch_for_new_drive(callback, stop_event)`: calls `callback(mountpoint)` when a new card is inserted.
- `scan_drive(drive_path, output_dir, log=print)`: copies `.srt .jpg .jpeg .dng .csv .txt .dat .mp4 .mov .gpx .kml` (skipping system folders such as `System Volume Information`) into `forensic_<timestamp>/raw_files/`, then processes the **local copies**: CSV maps, image EXIF to JSON, `.DAT` to `extracted/<name>_dat.csv`. Writes `report.json`. If no DJI files are found, it creates no folder.

`telemetry.py` is the DroneXtract map and ASCII chart tool. It works on any exported CSV without a drone attached:

```python
from telemetry import DJIFlightPathMap, DJITelemetryVisualizations
DJIFlightPathMap("flight.csv", "map.png").execute_flight_path_analysis()   # PNG map, needs staticmap + internet
DJITelemetryVisualizations("flight.csv").execute_telemetry_visualizations()  # menu of 45 channels, plotext chart
```

Running `python3 telemetry.py` gives the same two tools as an interactive menu. The chart menu lists all 45 channels (heights, speeds, attitude, RC sticks, gimbal, battery and cell voltages, `flyc_state`). Both tools downsample long logs; see `FLIGHT_MAP_DOWNSAMPLE` and `TELEMETRY_VIS_DOWNSAMPLE` below, which can also be set in a `.env` file at the repo root.

---

## drone_pipeline/: command-line entry point

```bash
python3 modules/digital_forensics/drone_pipeline/main.py scan [--output-dir DIR]   # default: data/extracted
python3 modules/digital_forensics/drone_pipeline/main.py run  path/to/flight.csv  # or .kml / .gpx
```

`scan` uses the first removable drive it finds. `run` parses one file. A CSV with `latitude`/`longitude` also gets a map and the interactive chart menu.

---

## Output files

Written into the session folder (`data/extracted/<session>/`) unless noted:

| File | Written by | Contents |
|------|------------|----------|
| `<name>_dat.csv` | `dat_parser` (via flight_logs, View CSV or the scanner) | Decoded `.DAT` records, one row per record |
| `flight_logs_parsed.txt` | `analyze_flight_logs` | All parser text output combined |
| `media_telemetry_<YYYY-MM-DD>.csv` | `analyze_media_telemetry` | One row per photo, video or IDX record |
| `media_telemetry_info.json` | `analyze_media_telemetry` | Files that could not be read, and when the CSVs were generated |
| `<stem>_flight_map.png` | `analyze_telemetry` | Flight path or capture-location map |
| `forensic_<ts>/raw_files/`, `extracted/`, `report.json` | `scanner.scan_drive` | SD Card Scan copy and results |

`data/` is git-ignored, so evidence never gets committed.

---

## Dependencies and configuration

| Package | Used by | Needed? |
|---------|---------|---------|
| `Pillow` | EXIF (media_metadata, media_telemetry, scanner) | Yes |
| `psutil` | Drive detection (scanner) | For SD Card Scan |
| `matplotlib` | Offline maps (analysis/telemetry) | For maps |
| `colorama`, `gpxpy` | DroneXtract parsers | For CSV/KML/GPX parsing |
| `staticmap`, `plotext`, `python-dotenv` | DroneXtract map and charts | Optional |

The `.DAT` decoder, stego scan and media-telemetry parsing of videos and IDX files use only the standard library.

| Environment variable | Default | Effect |
|----------------------|---------|--------|
| `INDRA_ONLINE_MAPS` | unset | `1` = try OpenStreetMap tiles before the offline map |
| `FLIGHT_MAP_DOWNSAMPLE` | `100` | Max points on the DroneXtract map |
| `TELEMETRY_VIS_DOWNSAMPLE` | `200` | Max points on the ASCII chart |

---

## Known limitations

- **Only Phantom 3 `.DAT` logs decode.** Phantom 4 and newer logs are usually encrypted. They are copied and flagged but produce no CSV. [DatCon](https://datfile.net/) can decode them; INDRA does not run it yet (`tools/DatCon/` is git-ignored).
- **`DJIFlightRecord*.txt` (DJI GO app logs) are only previewed**, not decoded. They need a decoder such as `dji-log-parser`.
- **`.csv`, `.kml` and `.gpx` from a hashed extraction are not parsed by Parse Logs.** `usb_extractor.py` puts only `.dat` and `.txt` in `flight_logs`, so those files land in `other`, which `analyze_flight_logs` never reads. The SD Card Scan and `drone_pipeline run` do handle them.
- **`.srt` subtitle telemetry** (per-frame GPS in DJI video subtitles) is copied but not decoded.
- **Drive detection is Linux only** (`/sys/block`). On macOS or Windows, type the card's path into the SD Card Scan box.
- **Stego screening** finds appended or embedded files only, not LSB or steghide payloads.
- **SD Card Scan does not hash files.** Use the extraction path for anything that needs chain of custody.
