"""
drone_pipeline/main.py

Unified entry point for the DroneXtract pipeline inside INDRA.

Two callable entry points:
    scan_sd_card(output_dir)  — detect SD card, extract all DJI files, run parsers
    run_pipeline(file_path)   — parse and visualise a single extracted file
"""

import os
import sys

# ── Path setup ────────────────────────────────────────────────────────────────
# _ROOT = modules/digital_forensics/
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PARSING  = os.path.join(_ROOT, "parsing")
_TELEMETRY = os.path.join(_ROOT, "telemetry")

for _p in (_PARSING, _TELEMETRY):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ── Entry points ──────────────────────────────────────────────────────────────

def scan_sd_card(output_dir: str, log=print) -> dict:
    """
    Detect an inserted SD card, extract all DJI files, and run all parsers.
    Returns the scanner summary dict (same as scan_drive()).
    """
    from scanner import get_usb_drives, scan_drive

    drives = get_usb_drives()
    if not drives:
        log("[!] No removable drives found. Insert SD card and try again.")
        return {}

    if len(drives) > 1:
        log(f"[*] Multiple drives found: {drives}")
        log(f"[*] Using first: {drives[0]}")

    drive = drives[0]
    log(f"[+] Scanning drive: {drive}")
    return scan_drive(drive, output_dir, log=log)


def run_pipeline(file_path: str) -> None:
    """
    Parse and visualise a single DJI file (.csv / .kml / .gpx).
    CSV files also get a flight-path map and telemetry chart menu.
    """
    if not os.path.isfile(file_path):
        print(f"[ERROR] File not found: {file_path}")
        return

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".csv":
        import csv as _csv
        with open(file_path, newline="", encoding="utf-8") as f:
            headers = [h.strip() for h in next(_csv.reader(f), [])]

        from parsers import DJI_CSV_Parser
        DJI_CSV_Parser(file_path).parse_contents()

        if "latitude" in headers and "longitude" in headers:
            from telemetry import DJIFlightPathMap
            map_out = os.path.splitext(file_path)[0] + "_flight_map.png"
            DJIFlightPathMap(file_path, map_out).execute_flight_path_analysis()

        if headers:
            from telemetry import DJITelemetryVisualizations
            DJITelemetryVisualizations(file_path).execute_telemetry_visualizations()

    elif ext == ".kml":
        from parsers import DJI_KML_Parser
        DJI_KML_Parser(file_path).parse_contents()

    elif ext == ".gpx":
        from parsers import DJI_GPX_Parser
        DJI_GPX_Parser(file_path).parse_contents()

    else:
        print(f"[*] {ext} files are copied during acquisition but not parsed directly.")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="INDRA drone pipeline")
    sub = parser.add_subparsers(dest="cmd")

    scan_p = sub.add_parser("scan", help="Scan an SD card")
    _default_out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "data", "extracted")
    scan_p.add_argument("--output-dir", default=_default_out)

    run_p = sub.add_parser("run", help="Process a single file")
    run_p.add_argument("file")

    args = parser.parse_args()

    if args.cmd == "scan":
        scan_sd_card(args.output_dir)
    elif args.cmd == "run":
        run_pipeline(args.file)
    else:
        parser.print_help()
