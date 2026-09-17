"""
Flight-log analysis for INDRA forensics.

Parses the flight-log files an extraction produced:
    .TXT - human-readable DJI flight record: line count, a short preview, and a
           crude delimiter guess.
    .DAT - binary DJI flight record: reports size and a hex header only. Full
           .DAT decoding (often encrypted) requires DROP-style tooling and is a
           separate open-source-tools / future task, not done here.

Python standard library only.
"""

import os


def analyze_flight_logs(manifest_path):
    """
    Analyze the flight_logs files listed in a session manifest.

    Returns a dict: {"log_count": n, "items": [ {per-file details} ]}.
    """
    from . import load_manifest, files_in_category

    manifest = load_manifest(manifest_path)
    logs = files_in_category(manifest, "flight_logs")
    items = []

    for e in logs:
        path = e.get("copied_path")
        ext = (e.get("file_type") or "").lower()
        entry = {
            "relative_path": e.get("relative_path"),
            "file_type": ext,
            "size_bytes": e.get("size_bytes"),
        }

        if not path or not os.path.exists(path):
            entry["status"] = "missing"
            items.append(entry)
            continue

        if ext == ".txt":
            try:
                with open(path, "r", errors="replace") as f:
                    content = f.read()
                lines = content.splitlines()
                entry["status"] = "parsed"
                entry["line_count"] = len(lines)
                entry["preview"] = lines[:15]
                if lines:
                    first = lines[0]
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
                entry["status"] = "binary"
                entry["header_hex"] = head.hex()
                entry["note"] = ("DJI .DAT is binary and often encrypted; full "
                                 "decode requires DROP-style tooling (future / "
                                 "open-source-tools task)")
            except Exception as ex:
                entry["status"] = f"error: {ex}"

        else:
            entry["status"] = "unrecognized flight-log type"

        items.append(entry)

    return {"log_count": len(logs), "items": items}
