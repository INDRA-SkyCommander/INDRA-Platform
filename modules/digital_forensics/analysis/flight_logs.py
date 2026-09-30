"""
Flight-log analysis for INDRA forensics.

Parses flight-log files from an extraction session:
    .csv - runs DJI_CSV_Parser (parsing), captures formatted output
    .kml - runs DJI_KML_Parser (parsing), captures formatted output
    .gpx - runs DJI_GPX_Parser (parsing), captures formatted output
    .txt - line count, preview, format guess (stdlib only)
    .dat - binary header hex (stdlib only)

All captured parser output is saved to flight_logs_parsed.txt in the session folder.
"""

import contextlib
import io
import os
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


def analyze_flight_logs(manifest_path: str) -> dict:
    """
    Analyze the flight_logs files listed in a session manifest.

    Returns:
        {
            "log_count": int,
            "items": [ {per-file details} ],
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

        # ── Existing stub behaviour for TXT / DAT ─────────────────────────
        elif ext == ".txt":
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

        elif ext == ".dat":
            try:
                with open(path, "rb") as f:
                    head = f.read(32)
                entry["status"]     = "binary"
                entry["header_hex"] = head.hex()
                entry["note"]       = ("DJI .DAT is binary and often encrypted; full "
                                       "decode requires DROP-style tooling.")
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

    return {"log_count": len(logs), "items": items, "output_file": output_file,
            "output_file_error": output_file_error}
