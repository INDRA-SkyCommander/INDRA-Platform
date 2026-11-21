"""
Telemetry analysis for INDRA forensics.

Generates a static PNG map for each CSV in a session that has latitude and
longitude columns: a flight path for decoded .DAT logs, numbered capture
locations for media telemetry. Offline (matplotlib) by default; the online
OpenStreetMap renderer is opt-in (INDRA_ONLINE_MAPS=1).
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


# Colours match the INDRA dark theme (IndraGUI.colors).
_MAP_BG, _MAP_PANEL, _MAP_TEXT, _MAP_MUTED = "#0d1117", "#161b22", "#e6edf3", "#8b949e"
_MAP_GRID, _MAP_ACCENT = "#30363d", "#2f81f7"
_M_PER_DEG_LAT = 110_540.0
_M_PER_DEG_LON_EQ = 111_320.0


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f not in (float("inf"), float("-inf")) else None


def _read_points(csv_path):
    """
    -> (kind, points, home). kind = "media" (snapshots from photos/videos/IDX),
    "dat" (decoded .DAT flight log) or "csv". points = [{lat, lon, label}] in
    file order; home = (lat, lon) or None.
    """
    with open(csv_path, newline="", encoding="utf-8", errors="replace") as f:
        reader = _csv.DictReader(f)
        cols = {c.lower(): c for c in (reader.fieldnames or [])}
        rows = list(reader)
    latk, lonk = cols.get("latitude"), cols.get("longitude")
    kind = "media" if "source_type" in cols else "dat" if "rec_type" in cols else "csv"
    home = None
    if kind == "dat":
        for r in rows:
            if r.get(cols["rec_type"]) == "HOME":
                la, lo = _num(r.get(cols.get("home_latitude", ""))), _num(r.get(cols.get("home_longitude", "")))
                if la and lo:
                    home = (la, lo)
                    break
        gps = [r for r in rows if r.get(cols["rec_type"]) == "GPS"]
        rows = gps or rows
    points = []
    if not latk or not lonk:
        return kind, points, home
    src_names = {"photo": "Photo", "video": "Video", "idx": "IDX"}
    for r in rows:
        la, lo = _num(r.get(latk)), _num(r.get(lonk))
        if not la or not lo:               # skip blank and 0,0 filler rows
            continue
        label = ""
        if kind == "media":
            t = (r.get(cols.get("timestamp", "")) or "")[11:19]
            src = src_names.get(r.get(cols.get("source_type", "")), "")
            label = f"{t}  {r.get(cols.get('source_file', ''), '')}  ({src})"
            if "not on the card" in (r.get(cols.get("notes", ""), "") or ""):
                label += " - video deleted"
        points.append({"lat": la, "lon": lo, "label": label})
    return kind, points, home


def _matplotlib_flight_map(csv_path: str, out_path: str) -> bool:
    """
    Offline renderer (no internet / map tiles needed). Returns True if a PNG was
    written.
      media telemetry -> "Capture locations": numbered points, no connecting
                         line (they are snapshots, not a path), with a key.
      .DAT / other    -> "Flight path": the track with start, end and home.
    Axes are metres east/north of the first point with equal scaling, so the
    shape is not distorted, distances read straight off the grid, and tick
    labels stay readable.
    """
    try:
        import math
        import matplotlib
        matplotlib.use("Agg")           # no display needed
        import matplotlib.pyplot as plt
    except Exception:
        return False

    try:
        kind, pts, home = _read_points(csv_path)
    except Exception:
        return False
    if len(pts) < (1 if kind == "media" else 2):
        return False

    lat0, lon0 = pts[0]["lat"], pts[0]["lon"]
    k_lon = _M_PER_DEG_LON_EQ * math.cos(math.radians(lat0))

    def xy(lat, lon):
        return (lon - lon0) * k_lon, (lat - lat0) * _M_PER_DEG_LAT

    xs, ys = zip(*(xy(p["lat"], p["lon"]) for p in pts))
    stem = os.path.splitext(os.path.basename(csv_path))[0]

    try:
        with plt.rc_context({"text.color": _MAP_TEXT, "axes.labelcolor": _MAP_MUTED,
                             "xtick.color": _MAP_MUTED, "ytick.color": _MAP_MUTED,
                             "axes.edgecolor": _MAP_GRID, "font.size": 10}):
            if kind == "media":
                fig, (ax, key) = plt.subplots(1, 2, figsize=(11, 6.4),
                                              gridspec_kw={"width_ratios": [3, 2]})
            else:
                fig, ax = plt.subplots(figsize=(8, 6.4))
                key = None
            fig.patch.set_facecolor(_MAP_BG)
            ax.set_facecolor(_MAP_PANEL)
            ax.grid(True, color=_MAP_GRID, linewidth=0.8)
            ax.set_axisbelow(True)

            if kind == "media":
                ax.scatter(xs, ys, s=150, color=_MAP_ACCENT, edgecolors=_MAP_TEXT,
                           linewidths=1.2, zorder=3)
                # Points within a couple of metres overlap; nudge labels in a ring.
                for i, (x, y) in enumerate(zip(xs, ys), start=1):
                    ang = (i - 1) * 2.4
                    ax.annotate(str(i), (x, y), xytext=(13 * math.cos(ang), 13 * math.sin(ang)),
                                textcoords="offset points", ha="center", va="center",
                                fontsize=9, fontweight="bold", color=_MAP_TEXT, zorder=4)
                day = stem.replace("media_telemetry_", "")
                ax.set_title(f"Capture locations · {day} · {len(pts)} point"
                             f"{'s' if len(pts) != 1 else ''}", loc="left",
                             fontsize=13, fontweight="bold", color=_MAP_TEXT)
                key.set_facecolor(_MAP_BG)
                key.axis("off")
                lines = [f"{i:>2}   {p['label']}" for i, p in enumerate(pts, start=1)]
                key.text(0.0, 1.0, "Key (in capture order)\n\n" + "\n".join(lines),
                         va="top", ha="left", family="monospace", fontsize=9,
                         color=_MAP_TEXT, transform=key.transAxes, linespacing=1.6)
                key.text(0.0, 0.0, "Snapshots taken when each photo was shot or a\n"
                                   "recording started - not a flight path, so the\n"
                                   "points are not joined.",
                         va="bottom", ha="left", fontsize=9, color=_MAP_MUTED,
                         transform=key.transAxes)
            else:
                ax.plot(xs, ys, "-", color=_MAP_ACCENT, linewidth=1.8, zorder=2)
                ax.scatter([xs[0]], [ys[0]], s=260, facecolors="none", edgecolors="#3fb950",
                           linewidths=2.2, zorder=5, label="start")
                ax.scatter([xs[-1]], [ys[-1]], s=90, color="#f85149", zorder=4, label="end")
                if home:
                    hx, hy = xy(*home)
                    ax.scatter([hx], [hy], s=110, marker="^", color="#d29922", zorder=4,
                               label="home point")
                leg = ax.legend(loc="best", facecolor=_MAP_BG, edgecolor=_MAP_GRID)
                for t in leg.get_texts():
                    t.set_color(_MAP_TEXT)
                name = stem[:-4] + ".DAT" if stem.lower().endswith("_dat") else stem
                ax.set_title(f"Flight path · {name} · {len(pts)} GPS points", loc="left",
                             fontsize=13, fontweight="bold", color=_MAP_TEXT)

            # Equal metres on both axes; never zoom tighter than 20 m across.
            cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
            half = max(max(xs) - min(xs), max(ys) - min(ys), 20.0) / 2 * 1.25
            ax.set_xlim(cx - half, cx + half)
            ax.set_ylim(cy - half, cy + half)
            ax.set_aspect("equal", adjustable="box")
            ax.ticklabel_format(useOffset=False, style="plain")
            ax.set_xlabel("metres east of first point")
            ax.set_ylabel("metres north of first point")

            ax.text(0.99, 0.01, f"first point {lat0:.6f}, {lon0:.6f}", ha="right", va="bottom",
                    fontsize=8, color=_MAP_MUTED, transform=ax.transAxes)

            fig.tight_layout(rect=(0, 0, 1, 0.97))
            fig.savefig(out_path, dpi=110, facecolor=fig.get_facecolor())
            plt.close(fig)
    except Exception:
        return False

    return os.path.exists(out_path) and os.path.getsize(out_path) > 0


def render_flight_map(csv_path: str, out_path: str, online=None) -> bool:
    """
    Render one CSV's points to out_path (PNG) with the offline renderer.

    The online renderer (staticmap) fetches OpenStreetMap tiles, which sends the
    flight's coordinates to a third party, so it is off by default for evidence.
    Set INDRA_ONLINE_MAPS=1 (or pass online=True) to try it first; the offline
    plot is the fallback either way. Returns True if a PNG was written.
    """
    if online is None:
        online = os.environ.get("INDRA_ONLINE_MAPS") == "1"
    if online:
        _ensure_telemetry_on_path()
        try:
            from telemetry import DJIFlightPathMap
            with open(os.devnull, "w") as _devnull, \
                 contextlib.redirect_stdout(_devnull):
                DJIFlightPathMap(csv_path, out_path).execute_flight_path_analysis()
        except Exception:
            pass
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return True
    return _matplotlib_flight_map(csv_path, out_path)


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
    session_dir = os.path.dirname(manifest_path)

    _ensure_telemetry_on_path()

    items = []
    maps_generated = 0

    # Collect every CSV flight log to map, from both sources:
    #   (a) the companion <name>_dat.csv that dat_parser writes next to a .dat
    #   (b) any other .csv anywhere in the session folder
    csv_paths = []
    for e in files_in_category(manifest, "flight_logs"):
        p = e.get("copied_path")
        if p and p.lower().endswith(".dat"):
            dat_csv = os.path.splitext(p)[0] + "_dat.csv"
            if os.path.isfile(dat_csv):
                csv_paths.append(dat_csv)
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

        if render_flight_map(path, map_out):
            entry["map_path"] = map_out
            maps_generated += 1
        else:
            entry["note"] = ("map not produced - install a renderer: "
                             "pip install matplotlib (offline) or pip install staticmap")

        items.append(entry)

    return {"maps_generated": maps_generated, "items": items}
