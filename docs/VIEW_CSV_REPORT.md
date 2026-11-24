# INDRA Platform — "View CSV" Investigation Report

Date: 2026-11-20  ·  Branch: `datFileTest` (HEAD `1c7b68a`)
Scope: how DJI Phantom 3 SD-card data flows into `data/extracted/`, and why the **View CSV** buttons in the Forensics tab do not open a CSV.

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

## 1. TL;DR (root cause)

**View CSV is not crashing — it has nothing to show, and it fails silently.**

1. **No DJI flight-log data exists in any extraction.** The SD card that was read (`/dev/sdb1`, exFAT, 238 GB, mounted at `/media/indra/disk`) is the **camera microSD card**. It only contains `DCIM/` (photos/videos), `MISC/` (thumbnails/index), `System Volume Information/`, and some planted CTF files (`secret.txt`, a `steghide` folder). There are **no `FLY###.DAT` files and no `DJIFlightRecord_*.txt` files** anywhere on the card or on this machine. The only `.dat` file is Windows' `WPSettings.dat` (12 bytes), which the DJI parser correctly rejects. → No `*_dat.csv` is ever written → there is no CSV to view.
   - Evidence: `flight_logs.json` → `"output_file": null`, WPSettings.dat status `dat_parse_failed: Not a DJI .dat file`; `telemetry.json` → `{"maps_generated": 0, "items": []}`.
2. **With the Session box blank, View CSV opens the wrong session.** `_resolve_session_dir("")` picks the newest folder by `manifest.json`/`report.json` mtime. The newest is `forensic_20261120_185822/` — an **empty** folder created by a failed SD Card Scan (see §4.3) — not `20261120_185559_6e7b40/`. That folder has zero files → zero CSVs.
3. **The "no CSV" outcome only writes one line to the terminal log panel** (`CSV viewer: no CSVs (or decodable .DAT files) in …`) and returns. No window, no popup, nothing in the card. To the user it looks like "the button does nothing."

Reproduced with the GUI's own methods (`_resolve_session_dir` + `_collect_session_csvs`) against the real data:
```
BLANK session field resolves to: data/extracted/forensic_20261120_185822
  -> ([], [])
Explicit 20261120_185559_6e7b40 ->
  ([], ["WPSettings.dat: Not a DJI .dat file (expected b'BUILD' at byte 16, ...)"])
```
The viewer window code itself (`_show_csv_viewer`) imports fine and is not the problem; it is simply never reached because `csvs == []`.

---

## 2. Where Phantom 3 flight data actually lives (important for the fix)

| Data | Where it is stored | On camera SD card? |
|---|---|---|
| Photos / videos (`DJI_####.JPG/.MOV`) | Camera microSD `DCIM/100MEDIA/` | **Yes** |
| Thumbnails / index (`MISC/THM`, `MISC/IDX`) | Camera microSD | **Yes** |
| `FLY###.DAT` (flight-controller binary log — what `dat_parser.py` decodes) | **Aircraft internal flight-controller storage**. Pulled by putting the aircraft in *Flight Data* mode (DJI GO → Settings → "Enter Flight Data Mode") and connecting the aircraft's micro-USB port to the PC; it mounts as a USB mass-storage volume. (Phantom 3 Standard differs — logs are not exposed the same way.) | **No** |
| `DJIFlightRecord_*.txt` (app flight record) | The **mobile device** running DJI GO (Android: `DJI/dji.go.v4/FlightRecord/` or `DJI/dji.pilot/FlightRecord/`; iOS via app file sharing) | **No** |
| `.SRT` per-frame telemetry subtitles | Only on models/firmware that write them; none on this card | No (here) |

So pointing the pipeline at the camera SD card will **never** yield a flight-log CSV, no matter how the viewer is coded. The test needs either the aircraft in Flight Data mode over USB, or a sample `FLY###.DAT` copied into a session.

Also note: even a real `DJIFlightRecord_*.txt` would **not** produce a CSV — the code only previews `.txt` lines (`analysis/flight_logs.py`), there is no TXT→CSV decoder.

---

## 3. Folder / data layout

### 3.1 Repo structure (relevant parts)
```
INDRA-Platform/
├── INDRA-Start.sh                  # sudo python3 src/main.py  (GUI runs as ROOT)
├── src/gui/IndraGUI.py             # Tkinter/ttkbootstrap GUI; Forensics tab + CSV viewer
├── forensics/acquisition/usb_extractor.py   # Pipeline A: "Acquisition" card
├── modules/digital_forensics/
│   ├── analysis/                   # Run by Parse Logs / Extract Metadata / Scan Images / Generate Map
│   │   ├── __init__.py             # load_manifest(), files_in_category()
│   │   ├── flight_logs.py          # analyze_flight_logs  -> flight_logs.json (+ *_dat.csv)
│   │   ├── telemetry.py            # analyze_telemetry    -> telemetry.json  (+ *_flight_map.png)
│   │   ├── media_metadata.py       # -> media_metadata.json
│   │   └── steganography.py        # -> steganography.json
│   ├── parsing/
│   │   ├── dat_parser.py           # parse_dat(dat, csv): Phantom 3 FLY.DAT -> CSV; summarize_dat_rows()
│   │   ├── dat_display.py          # column labels/legend for the viewer
│   │   └── parsers.py              # DJI_CSV/KML/GPX_Parser
│   ├── telemetry/
│   │   ├── scanner.py              # Pipeline B: "SD Card Scan" card (get_usb_drives, scan_drive)
│   │   └── telemetry.py            # DJIFlightPathMap, DJITelemetryVisualizations
│   └── drone_pipeline/main.py      # CLI wrapper around scanner (scan / run)
└── data/extracted/                 # git-ignored; all output, owned by root
```

### 3.2 There are TWO independent extraction pipelines with DIFFERENT layouts

**Pipeline A — Acquisition card → `forensics/acquisition/usb_extractor.py`**
- Detects sources via `lsblk -J` (mounted + USB/removable), copies every file, SHA-256 hashes, sorts by extension:
  - `.dat`, `.txt` → `flight_logs/`
  - images/videos → `media/`
  - everything else → `other/`
- Layout: `data/extracted/<YYYYMMDD_HHMMSS>_<6hex>/{flight_logs,media,other}/<label>/<original path>` + `manifest.json`
- The analysis cards (Parse Logs, Generate Map, etc.) **only work on these sessions** — they require `manifest.json` (`_resolve_manifest_path`) and write `<name>.json` into that folder.

**Pipeline B — SD Card Scan card → `modules/digital_forensics/telemetry/scanner.py::scan_drive`**
- Detects drives via `psutil.disk_partitions()` + `/sys/block/<dev>/removable` (needs `psutil`; it is **not installed** for the normal user's python3 — unknown for root's).
- Layout: `data/extracted/forensic_<YYYYMMDD_HHMMSS>/{raw_files/, extracted/, report.json}`; DAT → `extracted/<stem>_dat.csv`.
- No `manifest.json`, so analysis cards ignore these sessions — but View CSV's session picker does **not** ignore them (see §4.2).

### 3.3 What is actually in `data/extracted/` right now

| Folder | Created by | Contents |
|---|---|---|
| `20261120_183740_6eaed5/` | Pipeline A, 18:37 | `manifest.json` only — no source found (0 files) |
| `20261120_185559_6e7b40/` ("the one ending in 40") | Pipeline A, 18:55–18:56, source `/dev/sdb1` @ `/media/indra/disk` | 40 files (1.15 GB): `flight_logs` 10, `media` 9, `other` 21. Plus `manifest.json`, `report.txt`, `flight_logs.json`, `media_metadata.json`, `steganography.json`, `telemetry.json` |
| `forensic_20261120_185731/` | Pipeline B, 18:57 | `report.json` only, `source_drive: "20261120_185559_6e7b40"`, 0 files |
| `forensic_20261120_185822/` | Pipeline B, 18:58 | same as above, 0 files |

Contents of `20261120_185559_6e7b40/`:
```
flight_logs/sdb1/DCIM/100MEDIA/secret.txt                      ("obsfucationINDRA{devine_is_the_best}")
flight_logs/sdb1/DCIM/100MEDIA/steghide/steghide/*.txt         (8 steghide docs: README, LEAME, copying...)
flight_logs/sdb1/System Volume Information/WPSettings.dat      (Windows file, 12 B — NOT a DJI log)
media/sdb1/DCIM/100MEDIA/DJI_0002..0009.{JPG,MOV}, image.JPG   (real drone media)
other/sdb1/DCIM/100MEDIA/steghide.exe + steghide/steghide/*.dll, locale/...
other/sdb1/MISC/IDX/idx00, idx01     other/sdb1/MISC/THM/100/DJI_000{3,6,8,9}.THM
other/sdb1/System Volume Information/IndexerVolumeGuid
```
None of the 10 "flight_logs" are flight logs — they are miscategorised by extension only.

### 3.4 Data flow for a CSV (the intended happy path)
```
SD/aircraft  --(Acquisition)-->  session/flight_logs/.../FLY001.DAT
    --(Parse Logs: analyze_flight_logs -> dat_parser.parse_dat)-->  .../FLY001_dat.csv  + flight_logs.json
    --(Generate Map: analyze_telemetry)-->  session/FLY001_dat_flight_map.png + telemetry.json
    --(View CSV: _resolve_session_dir -> _collect_session_csvs [also decodes any undecoded .dat] -> _show_csv_viewer)--> window
```
`parse_dat` requires bytes 16–20 == `b"BUILD"` (Phantom 3 header), otherwise returns `csv_path: None` and **writes nothing**.

---

## 4. Code issues found (in priority order)

### 4.1 Silent failure when no CSV is found — `src/gui/IndraGUI.py` `_show_csv_viewer` (~line 2058)
```python
if not csvs:
    self._log(f"CSV viewer: no CSVs (or decodable .DAT files) in {session_dir}")
    return
```
Also errors from `_resolve_session_dir` only go to `self._log`. **Fix:** show a `messagebox.showinfo/showwarning` (or write into the card's results box) stating which session was searched, the `notes` (e.g. "WPSettings.dat: Not a DJI .dat file"), and that the camera SD card holds no flight logs.

### 4.2 Wrong session chosen when Session is blank — `_resolve_session_dir` (~line 1951)
Considers *every* subfolder of `data/extracted`, including empty `forensic_*` scan folders, and ranks by `manifest.json` **or** `report.json` mtime. The analysis cards use `_resolve_manifest_path` (manifest.json only), so "Parse Logs" and "View CSV" target **different sessions** when both are blank. **Fix options:** reuse `_resolve_manifest_path` semantics; or skip sessions containing no `.csv`/`.dat`; or pick the newest session that actually has a CSV/DAT.

### 4.3 SD Card Scan accepts an invalid drive path and creates empty sessions — `_handle_sd_scan` (~2547) + `scanner.scan_drive`
- The card's text box is labelled **"Session"** (shared `_make_analysis_card` template) but the SD scan uses it as a **drive path**. Someone typed the session ID `20261120_185559_6e7b40`; `scan_drive` did `os.walk("20261120_185559_6e7b40")` relative to CWD → nonexistent → 0 files, but still created `forensic_…/report.json`. Those empty folders then hijack §4.2.
- **Fix (applied, revised 2026-11-21):** the box takes a drive path **or** a session ID: a folder outside `data/extracted` is scanned as a drive, a session ID is processed in place, anything else shows an error. Blank auto-detects the card. `scan_drive` no longer creates a folder when 0 files are found.

### 4.4 SD card's "View CSV" ignores its own text box
`extra_buttons=[("View CSV", lambda: self._open_csv_viewer(None))]` (~line 1119) → always "most recent". Should pass `self.sd_card` or the scan's `output_dir`.

### 4.5 Over-broad flight-log categorisation — `usb_extractor.categorize`
`FLIGHT_LOG_EXTS = {".dat", ".txt"}` puts every text file and Windows `.dat` into `flight_logs/`. Suggest: only treat `.DAT` as a flight log if it starts with the DJI header (`b"BUILD"` at offset 16) or matches `FLY\d+\.DAT`; only `.txt` matching `DJIFlightRecord_*.txt`; skip `System Volume Information`. Also add `.csv`, `.kml`, `.gpx`, `.srt` (analysis/flight_logs.py already handles csv/kml/gpx but the extractor never routes them to `flight_logs`).

### 4.6 No decoder for DJI GO `.txt` flight records
If the team will pull `DJIFlightRecord_*.txt` from the phone, a TXT→CSV decoder (or an external tool like `dji-log-parser`/DatCon/TXTlogToCSVtool) is needed — otherwise View CSV will still find nothing.

### 4.7 Environment notes
- GUI runs as root via `INDRA-Start.sh` (`sudo python3`), so everything in `data/extracted` is root-owned. If any part is run as the `indra` user (e.g. from VS Code / standalone scripts), writes into session folders fail with `PermissionError` (the viewer has a fallback; the analysis cards don't).
- `psutil` is missing for the user's `python3`. If it is also missing for root, SD Card Scan auto-detect returns no drives.

---

## 5. How to verify a fix
1. Get a real Phantom 3 `FLY###.DAT` (aircraft in Flight Data mode over USB, or a sample file).
2. Copy it into a session: e.g. `sudo cp FLY001.DAT data/extracted/20261120_185559_6e7b40/flight_logs/sdb1/`.
3. Forensics tab → Flight Logs card → Session = `20261120_185559_6e7b40` → **Parse Logs** → expect `FLY001_dat.csv` next to the DAT and `output_file` set in `flight_logs.json`.
4. Click **View CSV** (same session) → window with GPS / Flight Status / Battery / RC / Home tabs + Map.
5. With Session blank, View CSV should resolve to the same session (after fixing §4.2), and with no logs it should show a visible message (after §4.1).

Quick non-GUI check of what View CSV will see:
```bash
cd ~/INDRA-Platform && python3 - <<'EOF'
import os, types, ast, textwrap
src = open('src/gui/IndraGUI.py').read()
cls = [n for n in ast.parse(src).body if isinstance(n, ast.ClassDef)][0]
ns = {'__file__': os.path.abspath('src/gui/IndraGUI.py')}; exec("import os, sys", ns)
for n in cls.body:
    if isinstance(n, ast.FunctionDef) and n.name in {'_resolve_session_dir','_collect_session_csvs'}:
        exec(textwrap.dedent(ast.get_source_segment(src, n, padded=True)), ns)
s = types.SimpleNamespace(); d = ns['_resolve_session_dir'](s, "")
print(d, ns['_collect_session_csvs'](s, d))
EOF
```
