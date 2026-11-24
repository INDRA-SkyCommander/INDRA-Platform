"""
Flight-log analysis for INDRA forensics.

Parses flight-log files from an extraction session:
    .csv - runs DJI_CSV_Parser (parsing), captures formatted output
    .kml - runs DJI_KML_Parser (parsing), captures formatted output
    .gpx - runs DJI_GPX_Parser (parsing), captures formatted output
    .txt - line count, preview, format guess (stdlib only)
    .dat - parsed directly by dat_parser (Python, no Java required);
           outputs a CSV alongside the .dat for telemetry map generation
"""

import contextlib
import io
import os
import re
import sys


def _ensure_parsing_on_path():
    """Add parsing/ to sys.path so parsers can be imported."""
    parsing_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "parsing")
    )
    if not os.path.isdir(parsing_dir):
        raise RuntimeError(
            f"parsing directory not found at {parsing_dir!r}. "
            "Ensure modules/digital_forensics/parsing exists."
        )
    if parsing_dir not in sys.path:
        sys.path.insert(0, parsing_dir)



def _capture_parser(parser_fn) -> str:
    """Run parser_fn() and return everything it printed as a string."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        parser_fn()
    return buf.getvalue()


def _fmt_dat_result(result: dict, csv_path: str) -> str:
    """Format dat_parser output as human-readable text for display and saved output."""
    import csv as _csv
    lines = [
        f"Records parsed : {result['records_parsed']}",
        f"Checksum errors: {result['checksum_errors']}",
        f"Header skip    : {result['header_skip']} bytes",
        f"CSV saved to   : {csv_path}",
        "",
    ]
    try:
        with open(csv_path, newline='', encoding='utf-8') as f:
            rows = list(_csv.DictReader(f))
        by_type: dict = {}
        for row in rows:
            rt = row.get('rec_type', 'UNKNOWN')
            by_type.setdefault(rt, []).append(row)

        for rec_type, type_rows in by_type.items():
            lines.append(f"── {rec_type} ({len(type_rows)} records) ──")
            sample = type_rows[0]
            for k, v in sample.items():
                if k != 'rec_type':
                    lines.append(f"   {k}: {v}")
            if len(type_rows) > 1:
                lines.append(f"   ... ({len(type_rows) - 1} more {rec_type} records)")
            lines.append("")
    except Exception as ex:
        lines.append(f"(could not summarise CSV: {ex})")
    return "\n".join(lines)


_DJI_RECORD_TXT = re.compile(r"^DJIFlightRecord", re.I)
_DJI_DAT_NAME = re.compile(r"^FLY\d+\.DAT$", re.I)


def _has_dji_dat_header(path: str) -> bool:
    """Phantom 3 style DJI .DAT: ASCII 'BUILD' at byte 16."""
    try:
        with open(path, "rb") as f:
            return f.read(21)[16:21] == b"BUILD"
    except OSError:
        return False


def _first_line(path: str, limit: int = 70) -> str:
    """First non-blank line of a text file, shortened - shown for skipped files."""
    try:
        with open(path, "r", errors="replace") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if line:
                    return line if len(line) <= limit else line[:limit - 1] + "…"
                if i > 50:
                    break
    except OSError:
        pass
    return ""


def _skip(entry: dict, reason: str, preview: str = "") -> dict:
    entry["status"] = "skipped"
    entry["skip_reason"] = reason
    if preview:
        entry["preview_line"] = preview
    return entry


def analyze_flight_logs(manifest_path: str) -> dict:
    """
    Analyze the flight_logs files listed in a session manifest.

    The extractor files every .txt/.dat under flight_logs by extension alone, so
    each file is checked first: real DJI flight logs (FLY###.DAT / DAT with the
    DJI header, DJIFlightRecord*.txt, .csv/.kml/.gpx) are parsed; anything else
    is reported as "skipped" with a reason instead of being dumped as a log.
    The session's media telemetry CSVs (GPS from photos/videos) are attached
    under "media_telemetry", since on a camera SD card they are the only
    flight data there is.

    Returns:
        {
            "log_count": int,          # real flight logs found
            "files_checked": int,      # files in the flight_logs category
            "skipped_count": int,
            "items": [ {per-file details} ],
            "media_telemetry": {csv_paths, groups, rows, with_gps, csv_error},
            "output_file": str | None   # path to saved flight_logs_parsed.txt
        }
    """
    from . import load_manifest, files_in_category

    manifest = load_manifest(manifest_path)
    logs = files_in_category(manifest, "flight_logs")
    items = []
    all_output_parts = []

    _ensure_parsing_on_path()

    for e in logs:
        path = e.get("copied_path")
        ext  = (e.get("file_type") or "").lower()
        entry = {
            "relative_path": e.get("relative_path"),
            "file_type":     ext,
            "size_bytes":    e.get("size_bytes"),
        }

        if not path or not os.path.exists(path):
            entry["status"] = "missing"
            items.append(entry)
            continue

        # ── Real parsers for CSV / KML / GPX ──────────────────────────────
        if ext == ".csv":
            try:
                from parsers import DJI_CSV_Parser
                captured = _capture_parser(lambda p=path: DJI_CSV_Parser(p).parse_contents())
                entry["status"]        = "parsed"
                entry["parsed_output"] = captured
                all_output_parts.append(f"=== {e.get('relative_path')} ===\n{captured}")
            except Exception as ex:
                entry["status"] = f"error: {ex}"

        elif ext == ".kml":
            try:
                from parsers import DJI_KML_Parser
                captured = _capture_parser(lambda p=path: DJI_KML_Parser(p).parse_contents())
                entry["status"]        = "parsed"
                entry["parsed_output"] = captured
                all_output_parts.append(f"=== {e.get('relative_path')} ===\n{captured}")
            except Exception as ex:
                entry["status"] = f"error: {ex}"

        elif ext == ".gpx":
            try:
                from parsers import DJI_GPX_Parser
                captured = _capture_parser(lambda p=path: DJI_GPX_Parser(p).parse_contents())
                entry["status"]        = "parsed"
                entry["parsed_output"] = captured
                all_output_parts.append(f"=== {e.get('relative_path')} ===\n{captured}")
            except Exception as ex:
                entry["status"] = f"error: {ex}"

        # ── TXT: only DJI GO flight records are flight logs ───────────────
        elif ext == ".txt" and not _DJI_RECORD_TXT.match(os.path.basename(path)):
            _skip(entry, "text file, not a DJI flight record", _first_line(path))

        elif ext == ".txt":
            entry["dji_flight_record"] = True
            entry["note"] = ("DJI GO flight record - not decoded yet "
                             "(needs a decoder such as dji-log-parser)")
            try:
                with open(path, "r", errors="replace") as f:
                    content = f.read()
                lines = content.splitlines()
                entry["status"]       = "parsed"
                entry["line_count"]   = len(lines)
                entry["preview"]      = lines[:15]
                first = lines[0] if lines else ""
                if "," in first:
                    entry["format_guess"] = "csv-like"
                elif "\t" in first:
                    entry["format_guess"] = "tab-separated"
                else:
                    entry["format_guess"] = "plain text"
            except Exception as ex:
                entry["status"] = f"error: {ex}"

        elif ext == ".dat" and not (_has_dji_dat_header(path)
                                    or _DJI_DAT_NAME.match(os.path.basename(path))):
            rel = (e.get("relative_path") or "").lower()
            _skip(entry, "Windows system file, not a DJI log"
                  if "system volume information" in rel
                  else "no DJI header (BUILD at byte 16), not a DJI flight log")

        elif ext == ".dat":
            # Parse the binary .dat directly with our Python parser.
            csv_path = os.path.splitext(path)[0] + "_dat.csv"
            try:
                from dat_parser import parse_dat
                result = parse_dat(path, csv_path)
                if result.get("csv_path"):
                    captured = _fmt_dat_result(result, csv_path)
                    entry["status"]          = "parsed"
                    entry["csv_path"]        = csv_path
                    entry["records_parsed"]  = result["records_parsed"]
                    entry["checksum_errors"] = result["checksum_errors"]
                    entry["parsed_output"]   = captured
                    # Expose the CSV path as a manifest-like entry so
                    # analyze_telemetry can generate a flight-path map from it.
                    entry["dat_csv_for_telemetry"] = csv_path
                    all_output_parts.append(
                        f"=== {e.get('relative_path')} (DAT parsed) ===\n{captured}"
                    )
                else:
                    entry["status"] = f"dat_parse_failed: {result.get('error', 'no rows produced')}"
            except Exception as ex:
                entry["status"] = f"error: {ex}"

        elif ext == ".srt":
            # DJI video subtitle: per-frame GPS / altitude / camera settings.
            entry["note"] = ("DJI video subtitle telemetry (per-frame GPS and altitude) "
                             "- not decoded yet")
            try:
                with open(path, "r", errors="replace") as f:
                    lines = f.read().splitlines()
                entry["status"]     = "parsed"
                entry["line_count"] = len(lines)
                entry["preview"]    = lines[:15]
            except Exception as ex:
                entry["status"] = f"error: {ex}"

        else:
            entry["status"] = "unrecognized flight-log type"

        items.append(entry)

    # ── Save combined parser output to file ───────────────────────────────
    output_file = None
    output_file_error = None
    if all_output_parts:
        session_dir = os.path.dirname(manifest_path)
        output_file = os.path.join(session_dir, "flight_logs_parsed.txt")
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("\n\n".join(all_output_parts))
        except OSError as exc:
            output_file = None
            output_file_error = str(exc)

    # ── Media telemetry (GPS/attitude snapshots from photos and videos) ───
    try:
        from .media_telemetry import media_telemetry_for_session
        media = media_telemetry_for_session(manifest_path)
    except Exception as ex:
        media = {"csv_paths": [], "groups": [], "csv_error": str(ex)}

    skipped = sum(1 for it in items if it.get("status") == "skipped")
    return {"log_count": len(items) - skipped, "files_checked": len(logs),
            "skipped_count": skipped, "items": items, "media_telemetry": media,
            "output_file": output_file, "output_file_error": output_file_error}
