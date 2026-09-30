"""
Telemetry analysis for INDRA forensics.

Generates a static PNG flight-path map for each CSV flight log in a session
that contains latitude and longitude columns. Uses DJIFlightPathMap from
telemetry. Requires the staticmap package.
"""

import contextlib
import csv as _csv
import os
import sys


def _ensure_telemetry_on_path():
    """Add telemetry/ to sys.path so DJIFlightPathMap can be imported."""
    tel_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "telemetry")
    )
    if tel_dir not in sys.path:
        sys.path.insert(0, tel_dir)


def _has_lat_lon(path: str) -> bool:
    """Return True if the CSV has both 'latitude' and 'longitude' header columns."""
    try:
        with open(path, newline="", encoding="utf-8", errors="replace") as f:
            headers = [h.strip() for h in next(_csv.reader(f), [])]
        return "latitude" in headers and "longitude" in headers
    except Exception:
        return False


def analyze_telemetry(manifest_path: str) -> dict:
    """
    Generate flight-path PNG maps for all CSV files in a session that have
    latitude/longitude columns.

    Returns:
        {
            "maps_generated": int,
            "items": [
                {
                    "relative_path": str,
                    "file_type": str,
                    "size_bytes": int,
                    "map_path": str,     # present on success
                    "note": str,         # present when map not generated
                }
            ]
        }
    """
    from . import load_manifest, files_in_category

    manifest = load_manifest(manifest_path)
    logs = files_in_category(manifest, "flight_logs")
    session_dir = os.path.dirname(manifest_path)

    _ensure_telemetry_on_path()

    items = []
    maps_generated = 0

    for e in logs:
        path = e.get("copied_path")
        ext  = (e.get("file_type") or "").lower()

        if ext != ".csv":
            continue

        entry = {
            "relative_path": e.get("relative_path"),
            "file_type":     ext,
            "size_bytes":    e.get("size_bytes"),
        }

        if not path or not os.path.exists(path):
            entry["note"] = "file missing"
            items.append(entry)
            continue

        if not _has_lat_lon(path):
            entry["note"] = "no latitude/longitude columns — map not generated"
            items.append(entry)
            continue

        rel = e.get("relative_path") or os.path.basename(path)
        stem = os.path.splitext(rel)[0].replace(os.sep, "_").replace("/", "_")
        map_out = os.path.join(session_dir, f"{stem}_flight_map.png")

        try:
            from telemetry import DJIFlightPathMap
            with open(os.devnull, "w") as _devnull, \
                 contextlib.redirect_stdout(_devnull):
                DJIFlightPathMap(path, map_out).execute_flight_path_analysis()
            entry["map_path"] = map_out
            maps_generated += 1
        except ImportError:
            entry["note"] = "staticmap not installed — run: pip install staticmap"
        except Exception as ex:
            entry["note"] = f"map generation failed: {ex}"

        items.append(entry)

    return {"maps_generated": maps_generated, "items": items}
