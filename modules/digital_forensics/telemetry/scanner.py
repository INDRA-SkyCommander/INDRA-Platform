"""
telemetry_python/scanner.py

USB drone detection and digital forensic extraction engine for Linux/Ubuntu.

Detects removable drives (drone SD card / internal storage), discovers all
DJI file types, copies them to a timestamped output folder, and runs
available extractions (flight path map, parsing, EXIF metadata).
"""

import csv
import json
import os
import re
import shutil
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

try:
    import psutil
except ImportError:
    psutil = None

# ── File types recognised as DJI forensic targets ────────────────────────────

SCAN_EXTENSIONS: Dict[str, str] = {
    '.srt': 'DJI Subtitle (per-frame telemetry)',
    '.jpg': 'JPEG Image',
    '.jpeg': 'JPEG Image',
    '.dng': 'DNG Raw Image',
    '.csv': 'CSV Flight Record',
    '.txt': 'TXT Flight Log',
    '.dat': 'Internal Flight Log (DAT)',
    '.mp4': 'MP4 Video',
    '.mov': 'MOV Video',
    '.gpx': 'GPX Track',
    '.kml': 'KML Track',
}

# Folders to skip during recursive scan
_SKIP_DIRS = {'system volume information', '$recycle.bin', 'found.000', '.spotlight-v100', '.trashes'}


# ── Drive detection (Linux/Ubuntu) ────────────────────────────────────────────

def _get_base_device(device_path: str) -> str:
    """Extract the base block device name from a partition path.

    Examples:
        /dev/sdb1   -> sdb
        /dev/mmcblk0p1 -> mmcblk0
        /dev/sdb    -> sdb
    """
    name = os.path.basename(device_path)
    # mmcblk0p1 -> mmcblk0  (SD card via built-in slot)
    m = re.match(r'(mmcblk\d+)', name)
    if m:
        return m.group(1)
    # sdb1 -> sdb  (SD card via USB reader)
    return name.rstrip('0123456789')


def _is_removable_linux(device_path: str) -> bool:
    """Return True if the block device is marked removable by the Linux kernel."""
    base = _get_base_device(device_path)
    try:
        with open(f"/sys/block/{base}/removable") as f:
            return f.read().strip() == "1"
    except (IOError, OSError):
        return False


def get_usb_drives() -> List[str]:
    """Return mount points of all removable/USB drives currently visible."""
    if psutil is None:
        return []
    return [
        part.mountpoint
        for part in psutil.disk_partitions(all=False)
        if _is_removable_linux(part.device)
    ]


def watch_for_new_drive(
    callback: Callable[[str], None],
    stop_event: threading.Event,
    interval: float = 2.0,
):
    """
    Poll for new removable drives every `interval` seconds.
    Calls callback(mountpoint) when a new removable drive appears.
    Stops when stop_event is set.
    """
    if psutil is None:
        return
    seen = {p.mountpoint for p in psutil.disk_partitions(all=False)}
    while not stop_event.wait(interval):
        current_parts = psutil.disk_partitions(all=False)
        current = {p.mountpoint for p in current_parts}
        for part in current_parts:
            if part.mountpoint not in seen and _is_removable_linux(part.device):
                callback(part.mountpoint)
        seen = current


# ── Main scan entry point ─────────────────────────────────────────────────────

def scan_drive(
    drive_path: str,
    output_dir: str,
    log: Callable[[str], None] = print,
) -> Dict:
    """
    Scan an SD card for DJI files, copy everything, and run all extractions.

    Parameters
    ----------
    drive_path : str
        Root path of the SD card (e.g. "/media/user/DRONE_SD").
    output_dir : str
        Parent folder for output. A timestamped subdirectory is created inside.
    log : callable
        Status message callback — called with a single string for each update.

    Returns
    -------
    dict
        Summary of everything found and extracted.
    """
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = Path(output_dir) / f"forensic_{timestamp}"
    session_dir.mkdir(parents=True, exist_ok=True)

    log(f"[+] Scan started:  {drive_path}")
    log(f"[+] Output folder: {session_dir}")

    # ── 1. Discover files ─────────────────────────────────────────────────────
    log("[*] Scanning for DJI files...")
    found: Dict[str, List[str]] = {ext: [] for ext in SCAN_EXTENSIONS}

    for root, dirs, files in os.walk(drive_path):
        dirs[:] = [d for d in dirs if d.lower() not in _SKIP_DIRS and not d.startswith('.')]
        for fname in files:
            ext = Path(fname).suffix.lower()
            if ext in SCAN_EXTENSIONS:
                full = os.path.join(root, fname)
                found[ext].append(full)
                log(f"    Found [{SCAN_EXTENSIONS[ext]}]  {fname}")

    total = sum(len(v) for v in found.values())
    log(f"[+] {total} DJI file(s) discovered")

    summary: Dict = {
        "timestamp":    timestamp,
        "source_drive": drive_path,
        "output_dir":   str(session_dir),
        "files_found":  {k.lstrip('.'): [Path(p).name for p in v] for k, v in found.items() if v},
        "extracted":    {},
    }

    if total == 0:
        log("[!] No DJI files found on this drive.")
        _write_report(summary, session_dir)
        return summary

    # ── 2. Copy all files ─────────────────────────────────────────────────────
    raw_dir = session_dir / "raw_files"
    raw_dir.mkdir(exist_ok=True)
    log("[*] Copying raw files from SD card...")
    # Track copied paths so processors work on local copies, not the SD card
    copied: Dict[str, List[str]] = {ext: [] for ext in SCAN_EXTENSIONS}
    for ext, paths in found.items():
        for src in paths:
            dest = _unique_dest(raw_dir, Path(src).name)
            shutil.copy2(src, dest)
            copied[ext].append(str(dest))
    log(f"[+] Raw files copied to {raw_dir}")

    # ── 3. Extract / process (all on local copies, not the SD card) ──────────
    results_dir = session_dir / "extracted"
    results_dir.mkdir(exist_ok=True)
    extracted: Dict = {}

    # CSV — parse data table + generate flight path map
    if copied['.csv']:
        log("[*] Processing CSV flight records...")
        extracted['csv'] = _process_csv_files(copied['.csv'], results_dir, log)

    # KML — parse coordinate data
    if copied['.kml']:
        log(f"[*] Parsing {len(copied['.kml'])} KML track file(s)...")
        extracted['kml'] = _process_kml_files(copied['.kml'], log)

    # GPX — parse track data
    if copied['.gpx']:
        log(f"[*] Parsing {len(copied['.gpx'])} GPX track file(s)...")
        extracted['gpx'] = _process_gpx_files(copied['.gpx'], log)

    # Images — extract EXIF metadata to JSON
    image_files = copied['.jpg'] + copied['.jpeg'] + copied['.dng']
    if image_files:
        log("[*] Extracting image EXIF metadata...")
        extracted['images'] = _process_images(image_files, results_dir, log)

    # SRT — per-frame telemetry, copy only
    if copied['.srt']:
        log(f"[*] {len(copied['.srt'])} SRT file(s) contain per-frame telemetry (altitude, GPS, speed).")
        extracted['srt'] = [Path(p).name for p in copied['.srt']]

    # DAT — proprietary binary format, copy only
    if copied['.dat']:
        log(f"[*] {len(copied['.dat'])} internal DAT log(s) found.")
        log("    [!] DAT files use DJI's proprietary binary format.")
        log("        Use DatCon (Java) or dji-log-parser for full decoding.")
        extracted['dat'] = [Path(p).name for p in copied['.dat']]

    # TXT flight logs, copy only
    if copied['.txt']:
        log(f"[*] {len(copied['.txt'])} TXT flight log(s) copied.")
        extracted['txt'] = [Path(p).name for p in copied['.txt']]

    # Video — copy only
    videos = copied['.mp4'] + copied['.mov']
    if videos:
        log(f"[*] {len(videos)} video file(s) copied.")
        extracted['video'] = [Path(p).name for p in videos]

    summary["extracted"] = extracted
    _write_report(summary, session_dir)
    log("[✓] Extraction complete.")
    log(f"[✓] Report: {session_dir / 'report.json'}")
    return summary


# ── Processors ────────────────────────────────────────────────────────────────

def _process_csv_files(paths: List[str], out_dir: Path, log: Callable) -> List[Dict]:
    _add_parsing_path()
    results = []
    for path in paths:
        name   = Path(path).stem
        result = {"file": Path(path).name}
        try:
            with open(path, newline='', encoding='utf-8', errors='replace') as f:
                records = list(csv.reader(f))
            if not records:
                continue
            columns = [c.strip() for c in records[0]]
            result["columns"]   = columns
            result["row_count"] = len(records) - 1

            # Parse and display formatted data table
            try:
                from parsers import DJI_CSV_Parser
                log(f"    Parsing data table for {Path(path).name}...")
                DJI_CSV_Parser(path).parse_contents()
            except Exception as e:
                log(f"    [!] Parsing failed: {e}")

            # Generate flight path map if lat/lon columns are present
            if "latitude" in columns and "longitude" in columns:
                map_out = str(out_dir / f"{name}_flight_map.png")
                log(f"    Generating flight path map for {Path(path).name}...")
                try:
                    from telemetry import DJIFlightPathMap
                    DJIFlightPathMap(path, map_out).execute_flight_path_analysis()
                    result["flight_map"] = map_out
                    log(f"    [✓] Map saved: {Path(map_out).name}")
                except Exception as e:
                    log(f"    [!] Map generation failed: {e}")
            else:
                log(f"    {Path(path).name}: no lat/lon columns — skipping map")
        except Exception as e:
            log(f"    [!] Could not read {Path(path).name}: {e}")
        results.append(result)
    return results


def _process_kml_files(paths: List[str], log: Callable) -> List[str]:
    _add_parsing_path()
    results = []
    for path in paths:
        try:
            from parsers import DJI_KML_Parser
            log(f"    Parsing {Path(path).name}...")
            DJI_KML_Parser(path).parse_contents()
            results.append(Path(path).name)
        except Exception as e:
            log(f"    [!] KML parsing failed for {Path(path).name}: {e}")
    return results


def _process_gpx_files(paths: List[str], log: Callable) -> List[str]:
    _add_parsing_path()
    results = []
    for path in paths:
        try:
            from parsers import DJI_GPX_Parser
            log(f"    Parsing {Path(path).name}...")
            DJI_GPX_Parser(path).parse_contents()
            results.append(Path(path).name)
        except Exception as e:
            log(f"    [!] GPX parsing failed for {Path(path).name}: {e}")
    return results


def _process_images(paths: List[str], out_dir: Path, log: Callable) -> List[Dict]:
    results = []
    for path in paths:
        name = Path(path).stem
        ext  = Path(path).suffix.lower()
        result = {"file": Path(path).name}
        if ext in ('.jpg', '.jpeg'):
            try:
                from PIL import Image
                from PIL.ExifTags import TAGS
                with Image.open(path) as img:
                    raw = img.getexif()
                exif = {TAGS.get(k, str(k)): _safe_str(v) for k, v in raw.items()}
                exif_path = out_dir / f"{name}_exif.json"
                with open(exif_path, 'w', encoding='utf-8') as f:
                    json.dump(exif, f, indent=2)
                result["exif_json"] = str(exif_path.name)
                log(f"    [✓] EXIF extracted: {exif_path.name}")
            except Exception as e:
                log(f"    [!] EXIF failed for {Path(path).name}: {e}")
                result["error"] = str(e)
        elif ext == '.dng':
            result["note"] = "DNG raw file — use exiftool for full metadata extraction"
            log(f"    [i] DNG copied: {Path(path).name} (use exiftool for metadata)")
        results.append(result)
    return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _add_parsing_path():
    """Ensure parsing is on sys.path for parser imports."""
    parsing_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "parsing")
    if parsing_dir not in sys.path:
        sys.path.insert(0, parsing_dir)


def _unique_dest(directory: Path, filename: str) -> Path:
    dest = directory / filename
    if not dest.exists():
        return dest
    stem, suffix = Path(filename).stem, Path(filename).suffix
    return directory / f"{stem}_{int(time.time())}{suffix}"


def _safe_str(value) -> str:
    try:
        return str(value)
    except Exception:
        return "<unreadable>"


def _write_report(summary: Dict, session_dir: Path):
    with open(session_dir / "report.json", 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
