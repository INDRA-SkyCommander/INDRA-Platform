"""
Media metadata analysis for INDRA forensics.

Extracts EXIF / image metadata (format, dimensions, camera make/model, capture
timestamp, and whether GPS data is embedded) from the media files an extraction
produced. Uses Pillow (already present via the GUI); degrades gracefully if
Pillow or EXIF is unavailable. Container metadata for video files is not parsed
in this first version.
"""

import os

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".dng", ".bmp", ".gif", ".heic"}


def _gps_to_decimal(dms, ref):
    """Convert an EXIF ((deg),(min),(sec)) rational tuple + ref to decimal degrees."""
    try:
        deg = float(dms[0]); minutes = float(dms[1]); seconds = float(dms[2])
        dec = deg + minutes / 60.0 + seconds / 3600.0
        if str(ref).upper() in ("S", "W"):
            dec = -dec
        return round(dec, 6)
    except Exception:
        return None


def _maps_link(lat, lon):
    return f"https://www.google.com/maps?q={lat},{lon}"


def _exif_for_image(path):
    """Return an EXIF/metadata dict for one image via Pillow. Never raises."""
    try:
        from PIL import Image, ExifTags
    except Exception:
        return {"exif_available": False, "note": "Pillow not available"}

    data = {"exif_available": True}
    try:
        with Image.open(path) as im:
            data["format"] = im.format
            data["dimensions"] = f"{im.width}x{im.height}"
            data["mode"] = im.mode

            exif = im.getexif()
            if exif:
                name_to_id = {name: tid for tid, name in ExifTags.TAGS.items()}

                def tag(name):
                    tid = name_to_id.get(name)
                    val = exif.get(tid) if tid is not None else None
                    return str(val).strip() if val is not None else None

                for key, name in (("camera_make", "Make"),
                                  ("camera_model", "Model"),
                                  ("datetime", "DateTime"),
                                  ("software", "Software")):
                    v = tag(name)
                    if v:
                        data[key] = v

                # GPSInfo IFD tag id is 0x8825 (34853): decode to decimal lat/lon.
                try:
                    gps = exif.get_ifd(0x8825)
                    if gps:
                        data["gps_present"] = True
                        # GPS tag ids: 1=LatRef 2=Lat 3=LonRef 4=Lon 6=Altitude
                        lat = _gps_to_decimal(gps.get(2), gps.get(1))
                        lon = _gps_to_decimal(gps.get(4), gps.get(3))
                        if lat is not None and lon is not None:
                            data["gps_lat"] = lat
                            data["gps_lon"] = lon
                            data["gps_maps_url"] = _maps_link(lat, lon)
                        alt = gps.get(6)
                        if alt is not None:
                            try:
                                data["gps_altitude_m"] = round(float(alt), 1)
                            except Exception:
                                pass
                except Exception:
                    pass
    except Exception as e:
        data["error"] = str(e)
    return data


def analyze_media(manifest_path):
    """
    Analyze the media files listed in a session manifest.

    Returns a dict: {"media_count": n, "items": [ {per-file metadata} ]}.
    """
    from . import load_manifest, files_in_category

    manifest = load_manifest(manifest_path)
    media = files_in_category(manifest, "media")
    items = []

    for e in media:
        path = e.get("copied_path")
        ext = (e.get("file_type") or "").lower()
        entry = {
            "relative_path": e.get("relative_path"),
            "file_type": ext,
            "size_bytes": e.get("size_bytes"),
        }

        if ext in IMAGE_EXTS and path and os.path.exists(path):
            entry.update(_exif_for_image(path))
        else:
            entry["exif_available"] = False
            entry["note"] = "non-image or unreadable; container metadata not parsed in v1"

        items.append(entry)

    return {"media_count": len(media), "items": items}
