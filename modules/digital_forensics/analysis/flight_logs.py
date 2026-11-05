"""
Flight-log analysis for INDRA forensics.

Parses flight-log files from an extraction session:
    .csv - runs DJI_CSV_Parser (parsing), captures formatted output
    .kml - runs DJI_KML_Parser (parsing), captures formatted output
    .gpx - runs DJI_GPX_Parser (parsing), captures formatted output
    .txt - line count, preview, format guess (stdlib only)
    .dat - converted to CSV via DatCon.jar (requires java), falls back to hex header

All captured parser output is saved to flight_logs_parsed.txt in the session folder.

DatCon setup: place DatCon.jar in <project>/tools/DatCon/DatCon.jar
  or ~/DatCon/DatCon.jar. Download from: https://datcon.limesite.com/
"""

import contextlib
import io
import os
import subprocess
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


def _find_datcon_jar():
    """Return absolute path to DatCon.jar if found in known locations, else None."""
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    candidates = [
        os.path.join(project_root, "tools", "DatCon", "DatCon.jar"),
        os.path.join(os.path.expanduser("~"), "DatCon", "DatCon.jar"),
        os.path.join(os.path.expanduser("~"), ".local", "share", "DatCon", "DatCon.jar"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _java_available() -> bool:
    try:
        subprocess.run(["java", "-version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return False


def _run_datcon(dat_path: str) -> tuple:
    """
    Convert a DJI .dat file to CSV using DatCon.jar.

    DatCon writes <basename>.csv next to the input file.

    Returns (csv_path, error_message). One will always be None.
    """
    jar = _find_datcon_jar()
    if not jar:
        return None, (
            "DatCon.jar not found. Place it at tools/DatCon/DatCon.jar "
            "or ~/DatCon/DatCon.jar. Download: https://datcon.limesite.com/"
        )

    if not _java_available():
        return None, "java not found in PATH — install a JRE to use DatCon."

    expected_csv = os.path.splitext(dat_path)[0] + ".csv"

    try:
        result = subprocess.run(
            ["java", "-jar", jar, dat_path],
            capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        return None, "DatCon timed out after 120s."
    except (OSError, subprocess.SubprocessError) as e:
        return None, f"DatCon failed to launch: {e}"

    if os.path.isfile(expected_csv):
        return expected_csv, None

    stderr = (result.stderr or "").strip()
    return None, f"DatCon exited {result.returncode} but no CSV produced. {stderr}"


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
            # Try DatCon conversion first; fall back to raw hex header.
            csv_path, datcon_err = _run_datcon(path)
            if csv_path:
                try:
                    from parsers import DJI_CSV_Parser
                    captured = _capture_parser(
                        lambda p=csv_path: DJI_CSV_Parser(p).parse_contents()
                    )
                    entry["status"]        = "parsed_via_datcon"
                    entry["csv_path"]      = csv_path
                    entry["parsed_output"] = captured
                    all_output_parts.append(
                        f"=== {e.get('relative_path')} (DatCon → CSV) ===\n{captured}"
                    )
                except Exception as ex:
                    entry["status"]   = f"datcon_csv_parse_error: {ex}"
                    entry["csv_path"] = csv_path
            else:
                # DatCon unavailable — read binary header as a fallback.
                try:
                    with open(path, "rb") as f:
                        head = f.read(32)
                    entry["status"]     = "binary_header_only"
                    entry["header_hex"] = head.hex()
                    entry["datcon_unavailable"] = datcon_err
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
