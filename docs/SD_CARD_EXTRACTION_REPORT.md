# INDRA Platform — SD Card Extraction & File Layout Report

Date: 2026-11-20 · Repo: `INDRA-Platform` · Branch: `datFileTest`
Purpose: explain exactly how the platform pulls files off the drone's SD card, how they are laid out on disk, what flight data the card actually contains, and what other ways exist to get real flight logs. Written so another engineer/AI can pick up from here.

Companion doc: `VIEW_CSV_REPORT.md` (why "View CSV" shows nothing, and the fixes already made).

> **Current status (2026-11-21, branch `datFileTest`, commits `41be33f`, `801f077`, `3cbd844`).** Everything below was written on 2026-11-20 and is kept as the investigation record; where it differs from this box, this box is right.
> - **View CSV:** dark tables sized to their rows, a Details panel with a short meaning per field, header tooltips, and a toggle for columns that are blank/0 in every row. Media files get a summary grid; `.DAT` files keep theirs.
> - **Card Findings tab** (and a CARD FINDINGS section in `report.txt`): renamed files (`image.JPG`), gaps in `DJI_####` (`DJI_0001`), files the camera did not make in DCIM (`secret.txt`, steghide), IDX records for deleted videos, unreadable files.
> - **SD Card Scan box** takes **either** a drive path (scans it) **or** a session ID (processes it in place); blank auto-detects, with a picker if several drives are attached. Nothing is ever written outside `data/extracted`.
> - **Blank Session** means the most recently created session on every card; each card's status shows the session it used. If that session has nothing to view, View CSV offers the newest one that does.
> - **Media telemetry:** a damaged file is skipped and listed instead of stopping the run; an IDX record that repeats a video on the card is merged into that video's row; groups split on a >2 h gap or a >5 km jump, not on the calendar date.
> - **Map:** offline by default (OpenStreetMap only with `INDRA_ONLINE_MAPS=1`); snapshots are numbered points with a key, `.DAT` logs a path; axes in metres.
> - **Exports** go to `data/exports/<session>/` as `export_…csv`, in Readable (Excel) or Raw (re-opens in View CSV) form.
> - **File sorting fixed:** `usb_extractor.categorize` now files `.dat`/`.txt` as flight logs only when they are DJI logs (`FLY###…DAT` / DJI header / `DJIFlightRecord*.txt`) and routes `.csv .kml .gpx .srt` to `flight_logs`; Windows `.dat` and stray `.txt` go to `other`.
> - **Still open:** no TXT/Phantom 4 DAT decoder, `psutil` on the VM, SD Card Scan has no hashes/manifest, real `FLY###.DAT` data.

---

## 1. Key findings (read first)

1. **The drone is a Phantom 4, not a Phantom 3.** Every photo and video reports camera model **`FC330`**, which is the DJI Phantom 4 camera. (Phantom 3 cameras are `FC300X` Pro, `FC300S` Advanced, `FC300C` Standard, `FC300XW` 4K.) Camera firmware string: `v01.19.5266`. The project's `.DAT` decoder (`modules/digital_forensics/parsing/dat_parser.py`) is written for the **Phantom 3** record format. Phantom 4 `.DAT` files use a different and generally **encrypted** layout, so this parser is unlikely to decode them as-is. Verify this with a real Phantom 4 `.DAT` before relying on it.
2. **The SD card is the camera's microSD card. It contains no flight logs.** On this drone family, the card only holds photos/videos (`DCIM`) and camera housekeeping (`MISC`). Flight logs are stored on the **aircraft's internal flight-controller storage** (`FLY###.DAT`) and on the **phone/tablet running the DJI GO 4 app** (`DJIFlightRecord_*.txt`). See §7.
3. **The card's media does contain flight telemetry snapshots** that the platform currently ignores. Each photo has GPS + DJI XMP flight data (altitude, aircraft/gimbal attitude, speeds), and each video has a DJI metadata block with GPS, speed and attitude at the start of recording. This is a usable fallback for location and timeline evidence. See §6.
4. The card also contains **planted / non-DJI files** (a CTF-style flag in `secret.txt`, a full `steghide` Windows install, Windows `System Volume Information`). The extractor files most of these under `flight_logs/` because it sorts by file extension alone.

---

## 2. Source device: the SD card as plugged in

- Block device `/dev/sdb1`, **exFAT**, **238.3 GB**, USB transport, removable, auto-mounted by Ubuntu at **`/media/indra/disk`** (via a USB SD-card reader).
- `lsusb` showed **no DJI vendor ID (`2ca3`)**, so `dji_device_detected: false`. Expected, because this is a card reader, not the aircraft.

Directory tree on the card (reconstructed from the extraction manifest; 40 files, 1,150,259,630 bytes):
```
/media/indra/disk/
├── DCIM/
│   └── 100MEDIA/                     ← DJI camera output folder
│       ├── DJI_0002.JPG  DJI_0004.JPG  DJI_0005.JPG  DJI_0007.JPG  image.JPG
│       ├── DJI_0003.MOV  DJI_0006.MOV  DJI_0008.MOV  DJI_0009.MOV
│       ├── secret.txt                ← planted: "obsfucationINDRA{devine_is_the_best}"
│       ├── steghide.exe              ← planted: Windows steghide 0.5.1 binary
│       └── steghide/steghide/        ← planted: steghide docs, cygwin DLLs, locale .mo, manuals
├── MISC/
│   ├── IDX/idx00, idx01              ← DJI camera recording-index files (see §6.3)
│   └── THM/100/DJI_000{3,6,8,9}.THM  ← video thumbnails (one per .MOV)
└── System Volume Information/        ← created by Windows when the card was mounted there
    ├── WPSettings.dat                ← 12-byte Windows file, NOT a DJI log
    └── IndexerVolumeGuid
```
Note: DJI names the original JPGs `DJI_####.JPG`. `image.JPG` breaks that pattern. Its EXIF is a DJI FC330 shot taken 5 s before `DJI_0002.JPG` at almost the same spot (and `DJI_0001` is missing), so it is probably a renamed `DJI_0001.JPG`. Worth flagging as a possible sign of tampering.

---

## 3. How extraction works (code walk-through)

There are **two independent extraction pipelines** in the GUI's Forensics tab. They produce **different folder layouts**.

### 3.1 Pipeline A — "Acquisition" card → `forensics/acquisition/usb_extractor.py` (`USBExtractor`)
This is the pipeline that created the session folder ending in `…6e7b40`.

1. **Launch:** `INDRA-Start.sh` runs `sudo python3 src/main.py`, so the GUI and all extraction run **as root**. Everything under `data/extracted/` is root-owned.
2. **Detect DJI (hint only):** runs `lsusb` and looks for vendor `2ca3` or the string "dji". A negative result does not stop the run.
3. **Find sources:** runs `lsblk -J -o NAME,MOUNTPOINT,RM,TRAN,VENDOR,MODEL,LABEL,SIZE,TYPE,FSTYPE` and keeps every volume that is **mounted** and (**USB transport or removable**), excluding `/`, `/boot`, `/boot/efi`, `/home`, `/var`, `/usr`. The card must already be mounted; the tool does not mount anything. Alternatively, `--source <path>` (CLI) skips detection.
4. **Session ID:** `YYYYMMDD_HHMMSS_<6 hex>` → `data/extracted/<session_id>/`.
5. **Copy:** `os.walk` over the mountpoint. Every file is copied with `shutil.copy2` (keeps mtimes) to `<session>/<category>/<label>/<original relative path>`. `<label>` is the volume label, or the device name if there is none (here `sdb1`). Nothing is skipped, including `System Volume Information`.
6. **Categorize by extension only** (`categorize()`):
   - `flight_logs` ← `.dat`, `.txt`
   - `media` ← `.jpg .jpeg .png .dng .tif .tiff .heic .bmp .gif .mp4 .mov .avi .mkv .m4v .mts .h264 .lrv .lrf`
   - `other` ← everything else (including `.srt`, `.csv`, `.kml`, `.gpx`, `.thm`, files with no extension)
7. **Hash:** SHA-256 of the **copied** file (1 MiB chunks). The source is not hashed before copying, so there is no source-vs-copy comparison. There is also no write-blocker; the source is only read, but it is mounted read-write by the OS.
8. **Manifest:** `<session>/manifest.json` records tool, schema_version, session_id, host, start/end UTC, `dji_device_detected`, sources (device, mountpoint, label, fstype, size, transport), and per file: `original_path`, `copied_path`, `relative_path`, `source_label`, `category`, `file_type`, `size_bytes`, `sha256`, `extracted_at`, plus errors and summary counts. Errors are recorded per file; one bad file never aborts the run.
9. If no source is found, a manifest with 0 files is still written. That's what produced the empty `20261120_183740_6eaed5/`.

### 3.2 Pipeline B — "SD Card Scan" card → `modules/digital_forensics/telemetry/scanner.py::scan_drive`
1. Detects drives with `psutil.disk_partitions()` + `/sys/block/<dev>/removable` (needs `psutil`; not installed for the normal user's python3). The box takes a drive path (scanned) or a session ID (processed in place: decodes any .DAT, builds the media telemetry CSVs); blank auto-detects.
2. Walks the drive, **skipping** `System Volume Information`, `$RECYCLE.BIN`, `FOUND.000`, `.Spotlight-V100`, `.Trashes` and dot-folders. It only picks up `.srt .jpg .jpeg .dng .csv .txt .dat .mp4 .mov .gpx .kml`.
3. Output: `data/extracted/forensic_YYYYMMDD_HHMMSS/` containing `raw_files/` (flat copies, renamed if names collide), `extracted/` (`<stem>_exif.json` per JPG, `<stem>_dat.csv` per decoded DAT, flight maps for CSVs), and `report.json`. It writes **no hashes and no manifest**, so the analysis cards and the integrity check can't use these sessions.
4. *Fixed:* a typed session ID is handled as a session and a typed folder as a drive (it used to walk any text as a drive path), and `scan_drive` no longer creates an empty folder when 0 files are found. The two existing `forensic_20261120_1857xx/` folders are leftovers from before this fix.

### 3.3 Post-extraction analysis (operates on Pipeline A sessions via `manifest.json`)
GUI buttons → functions in `modules/digital_forensics/analysis/` → JSON written into the session folder:

| Button | Function | Output | Result for `…6e7b40` |
|---|---|---|---|
| Parse Logs | `analyze_flight_logs` | `flight_logs.json` (+ `<stem>_dat.csv`, `flight_logs_parsed.txt`) | 10 "logs", all non-DJI text plus WPSettings.dat (rejected: no `BUILD` header). No CSV. |
| Extract Metadata | `analyze_media` | `media_metadata.json` | EXIF incl. GPS for 5 JPGs; MOVs marked "container metadata not parsed in v1" |
| Scan Images | `analyze_stego` | `steganography.json` | 5 images, 0 suspicious |
| Generate Map | `analyze_telemetry` | `telemetry.json` (+ `*_flight_map.png`) | 0 maps, because there is no CSV |
| Verify Integrity | GUI `_verify_session` | — | 40/40 hashes verified |
| Generate Report | GUI `_build_report_text` | `report.txt` | written |
| View CSV | GUI `_show_csv_viewer` | — | nothing to show (see `VIEW_CSV_REPORT.md`) |

---

## 4. Output layout on disk

```
/home/indra/INDRA-Platform/data/extracted/          (git-ignored, root-owned)
├── 20261120_183740_6eaed5/          Pipeline A, 18:37 — no source found; manifest.json only
├── 20261120_185559_6e7b40/          Pipeline A, 18:55–18:56 — THE SD CARD EXTRACTION
│   ├── manifest.json                full per-file inventory + SHA-256
│   ├── report.txt                   human-readable extraction/integrity report
│   ├── flight_logs.json             Parse Logs result   (output_file: null)
│   ├── media_metadata.json          Extract Metadata result
│   ├── steganography.json           Scan Images result
│   ├── telemetry.json               Generate Map result ({"maps_generated":0,"items":[]})
│   ├── flight_logs/sdb1/...         ← .txt/.dat by extension (none are real flight logs)
│   ├── media/sdb1/DCIM/100MEDIA/... ← 5 JPG + 4 MOV
│   └── other/sdb1/...               ← steghide exe/dll/mo/pdf, MISC/IDX, MISC/THM, SVI
├── forensic_20261120_185731/        Pipeline B, empty (report.json only, 0 files)
└── forensic_20261120_185822/        Pipeline B, empty (report.json only, 0 files)
```
The same card directory (e.g. `DCIM/100MEDIA/`) appears under several category roots, because each file is filed by its own extension.

### 4.1 Full file inventory — session `20261120_185559_6e7b40`
Extraction 2026-11-20 23:55:59 → 23:56:30 UTC, host `indra-ubuntu-22`, 40 files, 0 errors, integrity PASS.

| Category | Path on card | Type | Bytes | SHA-256 (prefix) |
|---|---|---|---|---|
| flight_logs | `DCIM/100MEDIA/secret.txt` | .txt | 36 | `ccb0d53b3bae…` |
| flight_logs | `DCIM/100MEDIA/steghide/steghide/LEAME.txt` | .txt | 6,841 | `5db8c76cdded…` |
| flight_logs | `DCIM/100MEDIA/steghide/steghide/README.txt` | .txt | 6,506 | `4033ed432c6f…` |
| flight_logs | `DCIM/100MEDIA/steghide/steghide/about-nls.txt` | .txt | 25,122 | `141a1e05753e…` |
| flight_logs | `DCIM/100MEDIA/steghide/steghide/bugs.txt` | .txt | 608 | `76152b418930…` |
| flight_logs | `DCIM/100MEDIA/steghide/steghide/copying.txt` | .txt | 18,318 | `2434a9fb1bcf…` |
| flight_logs | `DCIM/100MEDIA/steghide/steghide/credits.txt` | .txt | 912 | `aad9ec4d7db4…` |
| flight_logs | `DCIM/100MEDIA/steghide/steghide/history.txt` | .txt | 2,079 | `d14b38f2408d…` |
| flight_logs | `DCIM/100MEDIA/steghide/steghide/todo.txt` | .txt | 814 | `245ea7b409a6…` |
| flight_logs | `System Volume Information/WPSettings.dat` | .dat | 12 | `f95f527947d2…` |
| media | `DCIM/100MEDIA/DJI_0002.JPG` | .jpg | 5,018,720 | `74ffd939b95a…` |
| media | `DCIM/100MEDIA/DJI_0003.MOV` | .mov | 393,191,598 | `8c72eef15f90…` |
| media | `DCIM/100MEDIA/DJI_0004.JPG` | .jpg | 4,829,742 | `0e7761348f09…` |
| media | `DCIM/100MEDIA/DJI_0005.JPG` | .jpg | 5,052,008 | `e85559b959f0…` |
| media | `DCIM/100MEDIA/DJI_0006.MOV` | .mov | 545,753,040 | `e41ce78af294…` |
| media | `DCIM/100MEDIA/DJI_0007.JPG` | .jpg | 5,043,072 | `c29b379ae0e0…` |
| media | `DCIM/100MEDIA/DJI_0008.MOV` | .mov | 121,086,851 | `ddfae95e0b75…` |
| media | `DCIM/100MEDIA/DJI_0009.MOV` | .mov | 61,650,002 | `bc183bcbf509…` |
| media | `DCIM/100MEDIA/image.JPG` | .jpg | 5,004,121 | `e0f0c119f8da…` |
| other | `DCIM/100MEDIA/steghide.exe` | .exe | 595,968 | `3cae09664fcd…` |
| other | `DCIM/100MEDIA/steghide/steghide/cygiconv-2.dll` | .dll | 980,992 | `6a10dd64b675…` |
| other | `DCIM/100MEDIA/steghide/steghide/cygintl-2.dll` | .dll | 37,888 | `ca618177d22d…` |
| other | `DCIM/100MEDIA/steghide/steghide/cygjpeg-62.dll` | .dll | 134,656 | `9f0c281805b0…` |
| other | `DCIM/100MEDIA/steghide/steghide/cygmcrypt-4.dll` | .dll | 185,344 | `4afeb9217b49…` |
| other | `DCIM/100MEDIA/steghide/steghide/cygmhash-2.dll` | .dll | 134,656 | `8a9cca95cb43…` |
| other | `DCIM/100MEDIA/steghide/steghide/cygwin1.dll` | .dll | 967,522 | `8a73980f6d6a…` |
| other | `DCIM/100MEDIA/steghide/steghide/cygz.dll` | .dll | 61,440 | `3120e4721a20…` |
| other | `DCIM/100MEDIA/steghide/steghide/locale/de/LC_MESSAGES/steghide.mo` | .mo | 30,267 | `c2b49de67824…` |
| other | `DCIM/100MEDIA/steghide/steghide/locale/es/LC_MESSAGES/steghide.mo` | .mo | 29,198 | `2f94cd35c347…` |
| other | `DCIM/100MEDIA/steghide/steghide/locale/fr/LC_MESSAGES/steghide.mo` | .mo | 30,386 | `2e9bb3c848ff…` |
| other | `DCIM/100MEDIA/steghide/steghide/locale/ro/LC_MESSAGES/steghide.mo` | .mo | 30,028 | `5c02d713d478…` |
| other | `DCIM/100MEDIA/steghide/steghide/manual.pdf` | .pdf | 61,507 | `55cbfae16052…` |
| other | `DCIM/100MEDIA/steghide/steghide/manual_es.pdf` | .pdf | 63,678 | `ebf264d2685c…` |
| other | `MISC/IDX/idx00` | (none) | 37,027 | `6ab7d00eaf6d…` |
| other | `MISC/IDX/idx01` | (none) | 34,995 | `4df0c873c338…` |
| other | `MISC/THM/100/DJI_0003.THM` | .thm | 38,400 | `4c2028acd02c…` |
| other | `MISC/THM/100/DJI_0006.THM` | .thm | 38,400 | `d5057f5bc235…` |
| other | `MISC/THM/100/DJI_0008.THM` | .thm | 38,400 | `f022b6ccf292…` |
| other | `MISC/THM/100/DJI_0009.THM` | .thm | 38,400 | `9c9d0bbdf953…` |
| other | `System Volume Information/IndexerVolumeGuid` | (none) | 76 | `3375e0f41116…` |

---

## 5. What a DJI camera SD card normally contains

| Folder / file | Meaning | Forensic value |
|---|---|---|
| `DCIM/100MEDIA/DJI_####.JPG` (or `.DNG`) | Stills | EXIF (time, GPS, altitude, camera serial-ish fields) + DJI XMP (`drone-dji:*` attitude/speed/altitude) |
| `DCIM/100MEDIA/DJI_####.MOV`/`.MP4` | Video | DJI `udta` metadata atoms (GPS at record start, speed, attitude); newer models embed per-frame telemetry or write a `.SRT` |
| `DCIM/100MEDIA/DJI_####.SRT` | Per-frame subtitle telemetry | Not written by the Phantom 4; present on later models (Mavic/P4P with subtitles on) |
| `MISC/THM/100/*.THM` | Video thumbnails | Shows a video existed even if the video was deleted |
| `MISC/IDX/idx##` | Recording index / recovery data | Holds a copy of the video's header (`moov`), including GPS, attitude, model `FC330` and a recording timestamp. Can **survive deletion of the video** |
| `MISC/GIS/`, `MISC/LOG/` | Some models only | Not present here |
| **Flight logs** | **Not on the camera card** for this drone family | — |

---

## 6. Flight data that IS on this card (currently unused by the platform)

### 6.1 Photos — EXIF GPS + DJI XMP (`drone-dji:` namespace)
Each JPG's XMP has: `AbsoluteAltitude`, `RelativeAltitude`, `GimbalRoll/Yaw/PitchDegree`, `FlightRoll/Yaw/PitchDegree`, `FlightX/Y/ZSpeed`, `CamReverse`, `GimbalReverse`.

| File | EXIF time (camera local) | Lat, Lon | Abs alt (m) | Rel alt (m) | Aircraft yaw | Gimbal pitch |
|---|---|---|---|---|---|---|
| image.JPG | 2026-10-15 15:02:42 | 39.480986, -79.930248 | 541.4 | 0.00 | +155.6 | 0.0 |
| DJI_0002.JPG | 2026-10-15 15:02:47 | 39.480981, -79.930254 | 541.4 | 0.00 | +154.9 | 0.0 |
| DJI_0004.JPG | 2026-10-15 15:05:07 | 39.480948, -79.930131 | 540.8 | 0.00 | +154.9 | 0.0 |
| DJI_0005.JPG | 2026-10-15 15:05:14 | 39.480956, -79.930123 | 540.7 | 0.00 | +153.5 | 0.0 |
| DJI_0007.JPG | 2026-10-15 15:10:23 | 39.480875, -79.930167 | 542.9 | 0.00 | +72.5 | 0.0 |

`RelativeAltitude 0.00` and zero speeds mean all photos were taken **on the ground** (pre-takeoff or landed).

### 6.2 Videos — DJI `moov/udta` atoms
Atoms: `©xyz` (ISO-6709 GPS + altitude), `©xsp/©ysp/©zsp` (speeds m/s), `©fpt/©fyw/©frl` (aircraft pitch/yaw/roll), `©gpt/©gyw/©grl` (gimbal pitch/yaw/roll), `©mdl` / `mdl` (model `FC330`). Values are a snapshot at the **start of recording**, not a per-frame track.

| File | GPS (lat, lon, alt m) | Speed x/y/z | Aircraft yaw / roll | Gimbal pitch | File mtime |
|---|---|---|---|---|---|
| DJI_0003.MOV | 39.480950, -79.930216, +0.1 | 0/0/0 | +151.4 / 0.0 | 0.0 | Oct 15 11:04 (host clock) |
| DJI_0006.MOV | 39.480975, -79.930193, +0.0 | 0/0/0 | +150.1 / +0.5 | 0.0 | Oct 15 11:08 |
| DJI_0008.MOV | 39.480905, -79.930105, +0.0 | 1.0/0.5/0 | -176.0 / **+8.7** | 0.0 | Oct 15 11:11 |
| DJI_0009.MOV | **38.084978, -82.177029, +4.1** | 0/0/0 | -47.3 / 0.0 | **-33.1** | **Oct 28 13:12** |

**Observations:**
- There are two distinct sessions:
  - Oct 15: the photos and DJI_0003/0006/0008, all within about 15 m of 39.4810, -79.9302.
  - Oct 28: DJI_0009, ~270 km away at 38.0850, -82.1770, about 4 m above home with the gimbal tilted down.
- DJI_0008 shows motion at record start (speed > 0, roll 8.7°).
- DJI_0001 is missing from the card while `image.JPG` is present.
- The EXIF times are around 15:0x while the file mtimes are around 11:0x on the same day. That's probably a camera-clock vs. UTC/local offset (≈ 4 h, consistent with US Eastern EDT). Treat it as unverified.

### 6.3 `MISC/IDX/idx00`, `idx01`
They begin with the original card path, e.g. `C:\DCIM\100MEDIA\DJI_0009.MOV`, then a binary date block (e.g. `ea07 0a00 1c00 …` = 2026-10-28 …), then an embedded copy of the video's `moov` header, including the same `©xyz` GPS, attitude and `mdl FC330`. These are corroborating evidence, and they could recover the metadata of videos that were deleted from `DCIM`.

---

## 7. Where the real flight logs are, and other ways to get them

Ranked by forensic value. Each option needs to be confirmed against the actual aircraft/firmware/app version; the details are from public DJI-forensics knowledge, not tested here.

| # | Source | What you get | How to acquire | How to decode | Caveats |
|---|---|---|---|---|---|
| 1 | **Aircraft internal storage** (flight controller) | `FLY###.DAT`: full-rate (~200 Hz+) flight-controller log of every flight: GPS, IMU, motors, battery, RC, home point, errors | **DJI Assistant 2 (for Phantom)** on Windows/macOS: connect the aircraft's micro-USB port, power on, open *Flight Data*, select and export the DATs. On some firmware, DJI GO/GO 4 offers "Enter Flight Data Mode", which exposes the logs as USB mass storage that INDRA's Acquisition card can then pull directly. | **DatCon** (free, Java; the repo's `.gitignore` already reserves `/tools/DatCon/`) → CSV. INDRA's `dat_parser.py` is Phantom 3–only. | Phantom 4 DATs are typically encrypted; DatCon handles supported versions. Storage is limited, so oldest flights get overwritten. |
| 2 | **Mobile device running DJI GO 4** | `DJIFlightRecord_YYYY-MM-DD_[hh-mm-ss].txt` per flight (10 Hz GPS, altitude, speed, battery, RC, home, app messages), plus a mobile-side copy of aircraft DATs in `MCDatFlightRecords/` on many installs | Android: `Internal storage/DJI/dji.go.v4/FlightRecord/` (and `…/MCDatFlightRecords/`). Can be pulled over USB/MTP or `adb pull`. iOS: Finder/iTunes File Sharing → DJI GO 4, or a full-filesystem/backup acquisition. | **`dji-log-parser`** (open-source, Rust CLI/library; exports CSV/GeoJSON/KML). Newer log versions (v13+) are encrypted and need a free DJI developer API key to decrypt. Older versions decode offline. TXTlogToCSVtool and DatCon also read older TXT logs. | Web viewers (PhantomHelp Log Viewer, Airdata) work but **upload evidence to a third party**, which is not appropriate for case data. Use only on test data. |
| 3 | **DJI account cloud sync** | Same flight records as #2, if "sync flight records" was on | Log in to the pilot's account in DJI GO 4 on a clean device and sync; or legal process to DJI | as #2 | Needs credentials or legal authority. |
| 4 | **Media metadata already on the card** (§6) | Point fixes with time, GPS, altitude, attitude, speed: 5 photos + 4 video starts + IDX copies | Already extracted | Read EXIF GPS, the XMP `drone-dji:*` block, and MOV `udta` `©xyz…` atoms | Not a flight path, just snapshots. Still enough to place the drone at locations and times and to export a CSV/map. |
| 5 | **Video content** | Visual timeline/landmarks | Already extracted | Manual review / frame extraction | Phantom 4 doesn't burn in telemetry or write SRT. |
| 6 | **Deleted-file recovery on the SD card** | Deleted DJI_0001, deleted videos and their IDX/THM remnants | Image the card (`dd`/`dc3dd` to a .img, hash it), then carve with PhotoRec/`foremost`/Autopsy | — | The current extractor copies the live filesystem only; it does not image the card or recover deleted files. |

**Bottom line:** to get a real flight path/CSV, acquire from the **aircraft** (#1) or the **pilot's phone** (#2). Without those, the most that can be done from this SD card is option #4. The platform could easily produce a "media telemetry" CSV and map from the card today.

---

## 8. Gaps in the current code relative to the above

1. **`analysis/media_metadata.py`** reads EXIF GPS only. It ignores the DJI XMP `drone-dji:*` fields and skips MOV/MP4 container metadata ("container metadata not parsed in v1"). `MISC/IDX` is ignored entirely.
2. **`parsing/dat_parser.py`** targets the Phantom 3 DAT layout (`BUILD` at offset 16, XOR-by-tick records). Phantom 4 DATs need different handling, or a call out to DatCon.
3. **No decoder for `DJIFlightRecord_*.txt`.** `.txt` files are only previewed. A wrapper around `dji-log-parser` would fill this.
4. **Categorisation is by extension only** (`usb_extractor.categorize`). Every `.txt`/`.dat` lands in `flight_logs/`, while `.srt`/`.csv`/`.kml`/`.gpx` land in `other/`. Better rules: `FLY\d+\.DAT` and/or DJI header check; `DJIFlightRecord_*.txt`; route `.srt/.csv/.kml/.gpx` to `flight_logs`; skip `System Volume Information`.
5. **No physical imaging.** Only live files are copied, so there's no deleted-file recovery and no pre-copy source hash. Consider an optional `dd` image + hash step before the logical copy.
6. **Two pipelines, two layouts.** The SD Card Scan has no manifest or hashes, so its output can't be verified or analysed by the other cards. Consider making SD Card Scan call `USBExtractor` so there's one layout.
7. **`image.JPG` naming anomaly** and the missing `DJI_0001` could be flagged automatically (DJI sequence-gap and non-DJI-name check).

---

## 9. Suggested next steps (for implementation)

1. **[DONE — `modules/digital_forensics/analysis/media_telemetry.py`, run by the Extract Metadata button; writes `media_telemetry_<YYYY-MM-DD>.csv`, one per capture session so separate days aren't drawn as one flight]** **Quick win from data you already have:** extend `media_metadata.py` (or add `analysis/media_telemetry.py`) to:
   - parse XMP `drone-dji:*` from JPGs
   - parse the MOV `moov/udta` atoms `©xyz ©xsp ©ysp ©zsp ©fpt ©fyw ©frl ©gpt ©gyw ©grl ©mdl`
   - optionally parse `MISC/IDX/idx##` for embedded `moov` copies

   Then write `<session>/media_telemetry.csv` with columns `source_file,timestamp,latitude,longitude,altitude_m,rel_alt_m,speed_x,speed_y,speed_z,aircraft_pitch,aircraft_roll,aircraft_yaw,gimbal_pitch,gimbal_roll,gimbal_yaw,model`. Lowercase `latitude`/`longitude` headers mean the existing **Generate Map** and **View CSV** pick it up with no further changes.
2. **Get real logs:** pull `FLY###.DAT` from the aircraft with DJI Assistant 2 (or Flight Data mode + the Acquisition card). Decode with DatCon into `tools/DatCon/` and wire a fallback in `analysis/flight_logs.py` for non-P3 DATs.
3. **Phone logs:** add `.txt` detection for `DJIFlightRecord_*` and a `dji-log-parser` wrapper that outputs CSV into the session.
4. Tighten categorisation (§8.4) and unify the pipelines (§8.6).

---

### Appendix — reproduce the metadata findings
```bash
cd ~/INDRA-Platform/data/extracted/20261120_185559_6e7b40
# Photo XMP
python3 -I -c "import re,sys;b=open(sys.argv[1],'rb').read(200000);print(re.findall(rb'drone-dji:(\w+)=\"([^\"]*)\"',b))" media/sdb1/DCIM/100MEDIA/DJI_0002.JPG
# Video udta GPS
strings -n 6 media/sdb1/DCIM/100MEDIA/DJI_0009.MOV | grep -E '^[+-][0-9]+\.[0-9]+[+-]' | head -1
# IDX header
xxd other/sdb1/MISC/IDX/idx00 | head -8
```
