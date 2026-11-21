"""
Media telemetry for INDRA forensics.

The DJI camera SD card holds no flight logs, but its media carry flight
telemetry *snapshots*. This module collects them into CSVs in the session
folder, one per capture session (`media_telemetry_<YYYY-MM-DD>.csv`), with
lowercase `latitude`/`longitude` columns, so the existing "Generate Map" and
"View CSV" features pick them up unchanged.

Sources (stdlib + Pillow only):
    Photos (.jpg/.jpeg/.dng)  EXIF DateTimeOriginal + GPS, and the DJI XMP block
                              (drone-dji:AbsoluteAltitude, RelativeAltitude,
                              Flight/Gimbal Roll/Pitch/Yaw, FlightX/Y/ZSpeed).
    Videos (.mov/.mp4)        moov/mvhd creation time + duration, and DJI
                              moov/udta atoms: (c)xyz ISO-6709 GPS, (c)xsp/ysp/zsp
                              speeds, (c)fpt/fyw/frl aircraft attitude,
                              (c)gpt/gyw/grl gimbal attitude. Snapshot at the
                              start of recording, not a per-frame track.
    MISC/IDX/idx##            DJI recording-index files: original card path, a
                              date block, and a copy of the video's moov header
                              (same atoms as above). Can outlive a deleted video.

Observed on a Phantom 4 (FC330): the video (c)xyz altitude is height relative to
the take-off point, so it goes in rel_altitude_m. Timestamps are recorded
exactly as the device wrote them; `time_source` says which clock each one came
from (on the test card the camera clock ran ~4 h ahead of the file mtimes,
consistent with UTC vs US Eastern, but that is not assumed here).

Usage:
    from modules.digital_forensics.analysis import analyze_media_telemetry
    result = analyze_media_telemetry("/path/to/session/manifest.json")

    # CLI (from the repo root):
    python3 -m modules.digital_forensics.analysis.media_telemetry <manifest.json> [--out-dir DIR]
"""

import csv
import json
import math
import os
import re
import struct
from datetime import datetime, timedelta

PHOTO_EXTS = {".jpg", ".jpeg", ".dng"}
VIDEO_EXTS = {".mov", ".mp4"}

CSV_PREFIX = "media_telemetry"
# Consecutive geotagged points further apart than this start a new capture session.
SESSION_GAP_KM = 5.0
# ...and so does a gap in time longer than this (a flight crossing midnight stays whole).
SESSION_GAP_HOURS = 2.0
# Sidecar with files that could not be read, written next to the CSVs.
INFO_FILE = "media_telemetry_info.json"

COLUMNS = [
    "timestamp", "source_type", "source_file",
    "latitude", "longitude", "abs_altitude_m", "rel_altitude_m",
    "speed_x_ms", "speed_y_ms", "speed_z_ms",
    "aircraft_pitch_deg", "aircraft_roll_deg", "aircraft_yaw_deg",
    "gimbal_pitch_deg", "gimbal_roll_deg", "gimbal_yaw_deg",
    "duration_s", "camera_model", "time_source", "indexed_file", "relative_path", "sha256",
    "notes",
]

# XMP drone-dji field -> CSV column
_XMP_MAP = {
    "AbsoluteAltitude":   "abs_altitude_m",
    "RelativeAltitude":   "rel_altitude_m",
    "FlightXSpeed":       "speed_x_ms",
    "FlightYSpeed":       "speed_y_ms",
    "FlightZSpeed":       "speed_z_ms",
    "FlightPitchDegree":  "aircraft_pitch_deg",
    "FlightRollDegree":   "aircraft_roll_deg",
    "FlightYawDegree":    "aircraft_yaw_deg",
    "GimbalPitchDegree":  "gimbal_pitch_deg",
    "GimbalRollDegree":   "gimbal_roll_deg",
    "GimbalYawDegree":    "gimbal_yaw_deg",
}

# DJI udta atom (after the 0xA9 '(c)' byte) -> CSV column
_UDTA_MAP = {
    b"xsp": "speed_x_ms", b"ysp": "speed_y_ms", b"zsp": "speed_z_ms",
    b"fpt": "aircraft_pitch_deg", b"frl": "aircraft_roll_deg", b"fyw": "aircraft_yaw_deg",
    b"gpt": "gimbal_pitch_deg", b"grl": "gimbal_roll_deg", b"gyw": "gimbal_yaw_deg",
}

_ISO6709 = re.compile(r"([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)?")
_MAC_EPOCH = datetime(1904, 1, 1)

# Photos: the DJI XMP packet sits in the first APP1 segments.
_PHOTO_HEAD_BYTES = 256 * 1024
# The moov box of a DJI video is small (a few KB); refuse absurd sizes.
_MAX_MOOV_BYTES = 64 * 1024 * 1024


def _num(text):
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return None


# ── MP4 / QuickTime box helpers ───────────────────────────────────────────────

def _iter_boxes(buf, start=0, end=None):
    """Yield (type, payload_start, box_end) for boxes laid end-to-end in buf."""
    end = len(buf) if end is None else end
    pos = start
    while pos + 8 <= end:
        size, btype = struct.unpack_from(">I4s", buf, pos)
        header = 8
        if size == 1:
            if pos + 16 > end:
                return
            size = struct.unpack_from(">Q", buf, pos + 8)[0]
            header = 16
        elif size == 0:
            size = end - pos
        if size < header or pos + size > end:
            return
        yield btype, pos + header, pos + size
        pos += size


def _read_moov_from_file(path):
    """Return the raw bytes of the top-level moov box of an MP4/MOV, or None."""
    file_size = os.path.getsize(path)
    with open(path, "rb") as f:
        pos = 0
        while pos + 8 <= file_size:
            f.seek(pos)
            head = f.read(16)
            if len(head) < 8:
                return None
            size, btype = struct.unpack(">I4s", head[:8])
            if size == 1:
                size = struct.unpack(">Q", head[8:16])[0]
            elif size == 0:
                size = file_size - pos
            if size < 8:
                return None
            if btype == b"moov":
                if size > _MAX_MOOV_BYTES:
                    return None
                f.seek(pos)
                return f.read(size)
            pos += size
    return None


def _parse_moov(moov):
    """
    Parse a complete moov box (bytes, starting at its size field) into a dict
    of CSV columns: creation time, duration, DJI udta GPS/speed/attitude, model.
    """
    row = {}
    if len(moov) < 8 or moov[4:8] != b"moov":
        return row
    for btype, start, end in _iter_boxes(moov, 8):
        if btype == b"mvhd":
            version = moov[start]
            try:
                if version == 1:
                    created, _mod, timescale, duration = struct.unpack_from(">QQIQ", moov, start + 4)
                else:
                    created, _mod, timescale, duration = struct.unpack_from(">IIII", moov, start + 4)
                if created:
                    row["timestamp"] = (_MAC_EPOCH + timedelta(seconds=created)).isoformat(sep=" ")
                    row["time_source"] = "video header creation time (camera clock)"
                if timescale:
                    row["duration_s"] = round(duration / timescale, 2)
            except struct.error:
                pass
        elif btype == b"udta":
            row.update(_parse_udta(moov, start, end))
    return row


def _parse_udta(buf, start, end):
    row = {}
    for btype, s, e in _iter_boxes(buf, start, end):
        if btype[:1] != b"\xa9":
            continue
        # QuickTime text item: uint16 length, uint16 language, then the text.
        text = buf[s + 4:e].split(b"\x00", 1)[0].decode("latin-1", "replace").strip()
        key = btype[1:]
        if key == b"xyz":
            m = _ISO6709.match(text)
            if m:
                row["latitude"] = float(m.group(1))
                row["longitude"] = float(m.group(2))
                if m.group(3):
                    row["rel_altitude_m"] = float(m.group(3))
        elif key in _UDTA_MAP:
            v = _num(text)
            if v is not None:
                row[_UDTA_MAP[key]] = v
        elif key == b"mdl" and text and text != "0":
            row["camera_model"] = text
    # DJI also stores the camera model in a plain "mdl" text inside udta/meta.
    if "camera_model" not in row:
        m = re.search(rb"mdl([A-Z]{2}\d{3,4}[A-Z]{0,2})", buf[start:end])
        if m:
            row["camera_model"] = m.group(1).decode("ascii")
    return row


# ── Per-source extractors ─────────────────────────────────────────────────────

def _photo_row(path):
    row = {"source_type": "photo"}
    try:
        from PIL import Image
        with Image.open(path) as im:
            exif = im.getexif()
            if exif:
                model = exif.get(0x0110)
                if model:
                    row["camera_model"] = str(model).strip("\x00 ").strip()
                ex = exif.get_ifd(0x8769)            # Exif sub-IFD
                dt = ex.get(0x9003) or exif.get(0x0132)   # DateTimeOriginal / DateTime
                if dt:
                    dt = str(dt).strip("\x00 ")
                    try:
                        row["timestamp"] = datetime.strptime(dt, "%Y:%m:%d %H:%M:%S").isoformat(sep=" ")
                    except ValueError:
                        row["timestamp"] = dt
                    row["time_source"] = "photo EXIF DateTimeOriginal (camera clock)"
                gps = exif.get_ifd(0x8825)
                if gps:
                    lat = _dms_to_dec(gps.get(2), gps.get(1))
                    lon = _dms_to_dec(gps.get(4), gps.get(3))
                    if lat is not None and lon is not None:
                        row["latitude"], row["longitude"] = lat, lon
                    alt = _num(gps.get(6))
                    if alt is not None:
                        if gps.get(5) in (1, b"\x01"):
                            alt = -alt
                        row["abs_altitude_m"] = round(alt, 2)
    except Exception as ex:
        row["_error"] = f"EXIF: {ex}"

    try:
        with open(path, "rb") as f:
            head = f.read(_PHOTO_HEAD_BYTES)
        for key, val in re.findall(rb'drone-dji:(\w+)="([^"]*)"', head):
            col = _XMP_MAP.get(key.decode("ascii", "ignore"))
            v = _num(val.decode("ascii", "ignore"))
            if col and v is not None:
                row[col] = v              # XMP altitude overrides EXIF (more precise)
    except OSError as ex:
        row["_error"] = f"XMP: {ex}"
    return row


def _dms_to_dec(dms, ref):
    try:
        deg, minutes, seconds = (float(x) for x in dms)
    except Exception:
        return None
    dec = deg + minutes / 60.0 + seconds / 3600.0
    if str(ref).strip("\x00 ").upper() in ("S", "W"):
        dec = -dec
    return round(dec, 7)


def _video_row(path):
    row = {"source_type": "video"}
    try:
        moov = _read_moov_from_file(path)
        if moov:
            row.update(_parse_moov(moov))
        else:
            row["_error"] = "no moov box found"
    except (OSError, struct.error, ValueError, OverflowError) as ex:
        row["_error"] = f"unreadable video header ({type(ex).__name__}: {ex})"
    return row


def _idx_row(path):
    """DJI MISC/IDX/idx## file: original path, date block, embedded moov copy."""
    row = {"source_type": "idx"}
    try:
        with open(path, "rb") as f:
            data = f.read(_MAX_MOOV_BYTES)
    except OSError as ex:
        row["_error"] = str(ex)
        return row

    orig = data[:64].split(b"\x00", 1)[0].decode("latin-1", "replace")
    if orig:
        row["indexed_file"] = orig

    i = data.find(b"moov")
    if i >= 4:
        size = struct.unpack_from(">I", data, i - 4)[0]
        if 8 <= size <= len(data) - (i - 4):
            row.update(_parse_moov(data[i - 4:i - 4 + size]))

    # Date block observed at 0x4C: uint32 LE year, month, day, weekday, hour, min, sec.
    if "timestamp" not in row and len(data) >= 0x68:
        try:
            y, mo, d, _wd, h, mi, s = struct.unpack_from("<7I", data, 0x4C)
            row["timestamp"] = datetime(y, mo, d, h, mi, s).isoformat(sep=" ")
            row["time_source"] = "IDX record date (camera clock)"
        except (struct.error, ValueError):
            pass
    return row


def _is_idx(entry):
    rel = (entry.get("relative_path") or "").replace("\\", "/").upper()
    return "MISC/IDX/" in rel


# ── Public entry points ───────────────────────────────────────────────────────

def extract_media_telemetry(path, entry=None):
    """Return one telemetry row (dict) for a photo, video or IDX file, or None."""
    entry = entry or {}
    ext = os.path.splitext(path)[1].lower()
    if _is_idx(entry) or re.fullmatch(r"idx\d+", os.path.basename(path), re.I):
        row = _idx_row(path)
    elif ext in PHOTO_EXTS:
        row = _photo_row(path)
    elif ext in VIDEO_EXTS:
        row = _video_row(path)
    else:
        return None
    row["source_file"] = os.path.basename(path)
    row["relative_path"] = entry.get("relative_path") or os.path.basename(path)
    if entry.get("sha256"):
        row["sha256"] = entry["sha256"]
    return row


def analyze_media_telemetry(manifest_path, out_dir=None, manifest=None):
    """
    Build media telemetry CSVs from every photo, video and MISC/IDX file in an
    extraction session (any category). Rows are sorted by timestamp and split
    into capture sessions, one CSV each: <out_dir>/media_telemetry_<YYYY-MM-DD>.csv
    (see _group_sessions). out_dir defaults to the session folder.

    Returns:
        {
          "rows": int,              # rows written
          "with_gps": int,          # rows that have latitude/longitude
          "csv_paths": [str],
          "groups": [ {name, rows, first, last} ],
          "csv_error": str | None,
          "items": [ {source_file, source_type, timestamp, latitude, longitude, note?} ],
        }
    """
    from . import load_manifest

    # manifest may be passed in directly (SD Card Scan sessions have no manifest.json;
    # see manifest_from_folder).
    manifest = manifest if manifest is not None else load_manifest(manifest_path)
    rows, items, skipped = [], [], []
    card_names = {os.path.basename((e.get("relative_path") or e.get("copied_path") or ""))
                  .upper() for e in manifest.get("files", [])}

    for e in manifest.get("files", []):
        path = e.get("copied_path")
        if not path or not os.path.isfile(path):
            continue
        # One damaged file must never stop the whole card from being processed.
        try:
            row = extract_media_telemetry(path, e)
        except Exception as ex:      # noqa: BLE001 - recorded, not swallowed
            reason = f"{type(ex).__name__}: {ex}"
            skipped.append({"file": e.get("relative_path") or os.path.basename(path),
                            "reason": reason})
            items.append({"source_file": os.path.basename(path), "note": reason})
            continue
        if row is None:
            continue
        err = row.pop("_error", None)
        if err:
            skipped.append({"file": row.get("relative_path"), "reason": err})
        indexed = row.get("indexed_file")
        item = {k: row.get(k) for k in ("source_file", "source_type", "timestamp",
                                         "latitude", "longitude")}
        if indexed:
            item["indexed_file"] = indexed
        if err:
            item["note"] = err
        items.append(item)
        if any(row.get(k) is not None for k in COLUMNS
               if k not in ("source_type", "source_file", "indexed_file",
                            "relative_path", "sha256", "notes")):
            rows.append(row)

    rows = _merge_idx_rows(rows, card_names)

    rows.sort(key=lambda r: (r.get("timestamp") or "~", r.get("source_file") or ""))
    items.sort(key=lambda r: (r.get("timestamp") or "~", r.get("source_file") or ""))

    out_dir = out_dir or os.path.dirname(manifest_path)
    groups = _group_sessions(rows)
    csv_paths, csv_error = [], None
    try:
        _remove_previous_outputs(out_dir)
        for name, group in groups:
            path = os.path.join(out_dir, f"{CSV_PREFIX}_{name}.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
                w.writeheader()
                w.writerows(group)
            csv_paths.append(path)
        with open(os.path.join(out_dir, INFO_FILE), "w", encoding="utf-8") as f:
            json.dump({"skipped": skipped,
                       "generated": datetime.now().isoformat(timespec="seconds")}, f, indent=2)
    except OSError as ex:
        csv_error = str(ex)

    return {
        "rows": sum(len(g) for _n, g in groups) if csv_paths else 0,
        "with_gps": sum(1 for r in rows if r.get("latitude") is not None),
        "csv_paths": csv_paths,
        "groups": [{"name": n, "rows": len(g),
                    "first": g[0].get("timestamp"), "last": g[-1].get("timestamp")}
                   for n, g in groups],
        "csv_error": csv_error,
        "skipped": skipped,
        "items": items,
    }


def manifest_from_folder(folder):
    """A minimal manifest ({"files": [...]}) for a folder of copied card files,
    e.g. an SD Card Scan session's raw_files/ (which has no manifest.json)."""
    files = []
    for root, _dirs, names in os.walk(folder):
        for n in names:
            p = os.path.join(root, n)
            files.append({"copied_path": p,
                          "relative_path": os.path.relpath(p, folder).replace(os.sep, "/")})
    return {"files": files}


def media_telemetry_for_session(manifest_path):
    """
    Describe a session's media telemetry CSVs, building them only if none exist
    yet (an existing set and its maps are left untouched). Same keys as
    analyze_media_telemetry, minus "items".
    """
    session_dir = os.path.dirname(manifest_path)
    existing = sorted(
        os.path.join(session_dir, fn) for fn in os.listdir(session_dir)
        if re.fullmatch(re.escape(CSV_PREFIX) + r"_[\w-]+\.csv", fn))
    if not existing:
        result = analyze_media_telemetry(manifest_path)
        result.pop("items", None)
        return result

    groups, total, with_gps = [], 0, 0
    for path in existing:
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        times = sorted(r["timestamp"] for r in rows if r.get("timestamp"))
        groups.append({"name": os.path.basename(path)[len(CSV_PREFIX) + 1:-4],
                       "rows": len(rows),
                       "first": times[0] if times else None,
                       "last": times[-1] if times else None})
        total += len(rows)
        with_gps += sum(1 for r in rows if r.get("latitude"))
    return {"rows": total, "with_gps": with_gps, "csv_paths": existing,
            "groups": groups, "csv_error": None}


def _distance_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a["latitude"], a["longitude"],
                                                b["latitude"], b["longitude"]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def _parse_ts(text):
    try:
        return datetime.strptime((text or "")[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _group_sessions(rows):
    """
    Split time-sorted rows into capture sessions: a new session starts after a
    gap of more than SESSION_GAP_HOURS, or when the drone is more than
    SESSION_GAP_KM from the previous geotagged point. Keeps unrelated sessions
    from being drawn as one long "flight" without cutting a flight at midnight.
    Undated rows form their own group. Returns [(name, rows)], name =
    YYYY-MM-DD of the session's first point [_b, _c...] or "undated".
    """
    groups, last_gps, last_ts = [], None, None
    for r in rows:
        ts = _parse_ts(r.get("timestamp"))
        day = ts.strftime("%Y-%m-%d") if ts else "undated"
        has_gps = r.get("latitude") is not None and r.get("longitude") is not None
        new = (not groups
               or (ts is None) != (groups[-1][0] == "undated")
               or (ts and last_ts and (ts - last_ts).total_seconds() > SESSION_GAP_HOURS * 3600)
               or (has_gps and last_gps is not None
                   and _distance_km(last_gps, r) > SESSION_GAP_KM))
        if new:
            groups.append([day, []])
            last_gps = None
        groups[-1][1].append(r)
        if has_gps:
            last_gps = r
        if ts:
            last_ts = ts

    named, seen = [], {}
    for day, g in groups:
        n = seen.get(day, 0)
        seen[day] = n + 1
        named.append((day if n == 0 else f"{day}_{chr(ord('a') + n)}", g))
    return named


def _merge_idx_rows(rows, card_names):
    """
    An IDX record repeats the moov header of the video it indexes. When that
    video is on the card, fold the IDX row into the video's row (noted, not
    drawn twice). When the video is gone, keep the IDX row: it is the only
    trace of a deleted or moved recording.
    """
    videos = {(r.get("source_file") or "").upper(): r
              for r in rows if r.get("source_type") == "video"}
    out = []
    for r in rows:
        if r.get("source_type") != "idx":
            out.append(r)
            continue
        target = os.path.basename((r.get("indexed_file") or "").replace("\\", "/")).upper()
        if target and target in videos:
            v = videos[target]
            note = f"also indexed by {r.get('source_file')}"
            v["notes"] = f"{v['notes']}; {note}" if v.get("notes") else note
            continue
        if target and target not in card_names:
            r["notes"] = "indexed video is not on the card (deleted or moved)"
        elif target:
            r["notes"] = "indexed video is on the card but its header could not be read"
        out.append(r)
    return out


# ── Summary for the viewer ────────────────────────────────────────────────────

_DJI_NAME = re.compile(r"DJI_(\d{4})\.(JPG|JPEG|DNG|MOV|MP4)$", re.I)
_MEDIA_EXTS = PHOTO_EXTS | VIDEO_EXTS


def _num_or_none(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def summarize_media_rows(rows, card_files=None, skipped=None):
    """
    Summary + evidence flags for one media telemetry CSV (rows as read back by
    csv.DictReader). card_files = relative paths of every file on the card
    (from manifest.json) so naming anomalies can be flagged.
    """
    by_source = {}
    for r in rows:
        k = r.get("source_type") or "unknown"
        by_source[k] = by_source.get(k, 0) + 1
    times = sorted(t for t in (_parse_ts(r.get("timestamp")) for r in rows) if t)
    pts = [(la, lo) for la, lo in ((_num_or_none(r.get("latitude")), _num_or_none(r.get("longitude")))
                                   for r in rows) if la is not None and lo is not None]
    centre = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)) if pts else None
    spread = max((_distance_km({"latitude": centre[0], "longitude": centre[1]},
                               {"latitude": p[0], "longitude": p[1]}) * 1000 for p in pts),
                 default=None) if centre else None

    def col_max(key, fn=None):
        vals = [v for v in ((fn(r) if fn else _num_or_none(r.get(key))) for r in rows) if v is not None]
        return max(vals) if vals else None

    def hspeed(r):
        x, y = _num_or_none(r.get("speed_x_ms")), _num_or_none(r.get("speed_y_ms"))
        return math.hypot(x, y) if x is not None and y is not None else None

    flags = []
    files = [f.replace("\\", "/") for f in (card_files or [])]
    dcim = [f for f in files if "DCIM/" in f.upper()]
    numbers = set()
    for f in dcim:
        name = os.path.basename(f)
        ext = os.path.splitext(name)[1].lower()
        m = _DJI_NAME.match(name)
        if m:
            numbers.add(int(m.group(1)))
        elif ext in _MEDIA_EXTS:
            flags.append(f"{name}: photo/video without a DJI_#### name (renamed?)")
    if numbers:
        missing = [n for n in range(1, max(numbers) + 1) if n not in numbers]
        if missing:
            shown = ", ".join(f"DJI_{n:04d}" for n in missing[:6])
            more = f" and {len(missing) - 6} more" if len(missing) > 6 else ""
            flags.append(f"Gap in DJI numbering: {shown}{more} missing (deleted or renamed?)")
    foreign = sorted({f.split("/")[f.upper().split("/").index("DCIM") + 2]
                      if len(f.split("/")) > f.upper().split("/").index("DCIM") + 2 else f
                      for f in dcim
                      if os.path.splitext(f)[1].lower() not in _MEDIA_EXTS | {".thm"}
                      and not _DJI_NAME.match(os.path.basename(f))})
    if foreign:
        shown = ", ".join(foreign[:5]) + (f" and {len(foreign) - 5} more" if len(foreign) > 5 else "")
        flags.append(f"Non-camera files in DCIM: {shown}")
    for r in rows:
        if "not on the card" in (r.get("notes") or ""):
            flags.append(f"{r.get('source_file')} indexes "
                         f"{os.path.basename(r.get('indexed_file') or '?')}, which is not on the card")
    for s_ in skipped or []:
        flags.append(f"Could not read {os.path.basename(s_.get('file') or '?')}: {s_.get('reason')}")

    models = sorted({r.get("camera_model") for r in rows if r.get("camera_model")})
    return {
        "points": len(rows),
        "by_source": by_source,
        "start": times[0] if times else None,
        "end": times[-1] if times else None,
        "length_s": (times[-1] - times[0]).total_seconds() if len(times) > 1 else None,
        "centre": centre,
        "spread_m": spread,
        "max_abs_alt_m": col_max("abs_altitude_m"),
        "max_rel_alt_m": col_max("rel_altitude_m"),
        "max_hspeed_ms": col_max(None, hspeed),
        "camera_models": models,
        "flags": flags,
    }


def _remove_previous_outputs(out_dir):
    """Delete CSVs/maps from an earlier run so stale sessions don't linger."""
    if not os.path.isdir(out_dir):
        return
    for fn in os.listdir(out_dir):
        if re.fullmatch(re.escape(CSV_PREFIX) + r"_[\w-]+(?:_flight_map\.png|\.csv)", fn):
            os.remove(os.path.join(out_dir, fn))


if __name__ == "__main__":
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Build media_telemetry_<date>.csv files for a session.")
    ap.add_argument("manifest", help="path to a session's manifest.json")
    ap.add_argument("--out-dir", help="output folder (default: the session folder)")
    args = ap.parse_args()
    print(json.dumps(analyze_media_telemetry(args.manifest, args.out_dir), indent=2))
