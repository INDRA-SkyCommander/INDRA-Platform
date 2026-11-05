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
            headers = [h.strip().lower() for h in next(_csv.reader(f), [])]
        return "latitude" in headers and "longitude" in headers
    except Exception:
        return False


def _matplotlib_flight_map(csv_path: str, out_path: str) -> bool:
    """
    Offline fallback renderer: plot the lat/lon flight path with matplotlib
    (no internet / map tiles needed). Returns True if a PNG was written.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")           # no display needed
        import matplotlib.pyplot as plt
    except Exception:
        return False

    lats, lons = [], []
    try:
        with open(csv_path, newline="", encoding="utf-8", errors="replace") as f:
            reader = _csv.DictReader(f)
            cols = {c.lower(): c for c in (reader.fieldnames or [])}
            latk, lonk = cols.get("latitude"), cols.get("longitude")
            if not latk or not lonk:
                return False
            for row in reader:
                try:
                    la, lo = float(row[latk]), float(row[lonk])
                except (TypeError, ValueError, KeyError):
                    continue
                if la or lo:               # skip 0,0 filler rows
                    lats.append(la); lons.append(lo)
    except Exception:
        return False

    if len(lats) < 2:
        return False

    try:
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.plot(lons, lats, "-", color="#2563a8", linewidth=1.5)
        ax.plot(lons[0], lats[0], "o", color="green", label="start")
        ax.plot(lons[-1], lats[-1], "o", color="red", label="end")
        ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
        ax.set_title("Flight path"); ax.legend(); ax.grid(True, alpha=0.3)
        fig.savefig(out_path, dpi=100, bbox_inches="tight")
        plt.close(fig)
    except Exception:
        return False

    return os.path.exists(out_path) and os.path.getsize(out_path) > 0


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
    session_dir = os.path.dirname(manifest_path)

    _ensure_telemetry_on_path()

    items = []
    maps_generated = 0

    # Find every .csv in the session folder: extracted CSV flight logs AND the
    # CSVs DatCon writes next to each decoded .DAT. Relying on the manifest's
    # flight_logs category missed both (the extractor files .csv as 'other', and
    # DatCon's output is created after extraction so it isn't in the manifest).
    csv_paths = []
    for root, _dirs, files in os.walk(session_dir):
        for fn in files:
            if fn.lower().endswith(".csv"):
                csv_paths.append(os.path.join(root, fn))

    for path in sorted(set(csv_paths)):
        entry = {
            "relative_path": os.path.relpath(path, session_dir),
            "file_type":     ".csv",
            "size_bytes":    os.path.getsize(path) if os.path.exists(path) else None,
        }

        if not _has_lat_lon(path):
            entry["note"] = "no latitude/longitude columns — map not generated"
            items.append(entry)
            continue

        stem = os.path.splitext(os.path.basename(path))[0]
        map_out = os.path.join(session_dir, f"{stem}_flight_map.png")

        # 1) Primary renderer: staticmap (downloads OSM tiles - needs internet).
        try:
            from telemetry import DJIFlightPathMap
            with open(os.devnull, "w") as _devnull, \
                 contextlib.redirect_stdout(_devnull):
                DJIFlightPathMap(path, map_out).execute_flight_path_analysis()
        except Exception:
            pass

        # 2) Offline fallback: matplotlib path plot (no internet) if no PNG yet.
        produced = os.path.exists(map_out) and os.path.getsize(map_out) > 0
        if not produced:
            produced = _matplotlib_flight_map(path, map_out)

        # Only count it if a map file was actually written.
        if produced:
            entry["map_path"] = map_out
            maps_generated += 1
        else:
            entry["note"] = ("map not produced - install a renderer: "
                             "pip install staticmap (needs internet) "
                             "or pip install matplotlib (offline)")

        items.append(entry)

    return {"maps_generated": maps_generated, "items": items}
