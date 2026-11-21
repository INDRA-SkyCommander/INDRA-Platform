"""
Display helpers for decoded DJI .DAT CSVs (used by the Forensics-tab viewer).

The CSV written by dat_parser keeps raw column names and values; everything
here only changes how they are shown.
"""

import math

# DJI flight-controller state (flyc_state) codes, as used by DatCon / DJI SDK.
FLIGHT_MODES = {
    0: "Manual", 1: "Atti", 2: "Atti Course Lock", 3: "Atti Hover", 4: "Hover",
    5: "GPS Brake", 6: "P-GPS", 7: "GPS Course Lock", 8: "GPS Home Lock",
    9: "GPS Hot Point", 10: "Assisted Takeoff", 11: "Auto Takeoff", 12: "Auto Landing",
    13: "Atti Landing", 14: "GPS Waypoint", 15: "Go Home", 16: "Click Go",
    17: "Joystick", 23: "Atti Limited", 24: "GPS Atti Limited", 25: "Follow Me",
    26: "ActiveTrack", 27: "TapFly", 28: "Pano", 29: "Farming", 30: "FPV",
    31: "Sport", 32: "Novice", 33: "Confirm Landing", 35: "Terrain Follow",
    36: "Advanced Go Home", 37: "Advanced Landing", 38: "Tripod", 39: "Track Headlock",
    41: "Engine Start", 43: "Gentle GPS",
}

# Reason GPS positioning is unavailable (non_gps_error).
GPS_STATUS = {
    0: "OK", 1: "Forbidden", 2: "Too few satellites", 3: "Poor GPS accuracy (HDOP)",
    4: "Position mismatch", 5: "Speed error", 6: "Yaw error", 7: "Compass error",
}

# Modes that mean the aircraft is flying itself home / landing.
AUTO_RETURN_MODES = {12, 13, 15, 33, 36, 37}

COLUMN_LABELS = {
    # shared
    "time_s":          "Time (s)",
    "tick":            "Clock Tick",
    # GPS
    "latitude":        "Latitude",
    "longitude":       "Longitude",
    "altitude_m":      "GPS Altitude (m)",
    "baro_alt_m":      "Barometric Altitude (m)",
    "pitch_deg":       "Pitch (°)",
    "roll_deg":        "Roll (°)",
    "yaw_deg":         "Heading (°)",
    "vel_n_ms":        "North Speed (m/s)",
    "vel_e_ms":        "East Speed (m/s)",
    "vel_d_ms":        "Descent Speed (m/s)",
    "satnum":          "GPS Satellites",
    # Flight status
    "height_m":        "Height Above Takeoff (m)",
    "flyc_state":      "Flight Mode",
    "connected_to_rc": "RC Connected",
    "failure":         "Failure",
    "non_gps_error":   "GPS Status",
    "flight_time_ms":  "Flight Time",
    # Battery
    "batt_remcap_mah": "Remaining Capacity (mAh)",
    "batt_volts":      "Pack Voltage (V)",
    "batt_amps":       "Current Draw (A)",
    "batt_percent":    "Charge (%)",
    "batt_temp_c":     "Battery Temp (°C)",
    "cell1_v":         "Cell 1 (V)",
    "cell2_v":         "Cell 2 (V)",
    "cell3_v":         "Cell 3 (V)",
    "cell4_v":         "Cell 4 (V)",
    # RC sticks
    "aileron":         "Roll Stick (Aileron)",
    "elevator":        "Pitch Stick (Elevator)",
    "throttle":        "Throttle Stick",
    "rudder":          "Yaw Stick (Rudder)",
    # Home point
    "home_latitude":   "Home Latitude",
    "home_longitude":  "Home Longitude",
    # Media telemetry (media_telemetry_<date>.csv from photos/videos/IDX)
    "timestamp":          "Time",
    "source_type":        "Source",
    "source_file":        "File",
    "abs_altitude_m":     "Altitude MSL (m)",
    "rel_altitude_m":     "Height Above Takeoff (m)",
    "speed_x_ms":         "Speed X (m/s)",
    "speed_y_ms":         "Speed Y (m/s)",
    "speed_z_ms":         "Speed Z (m/s)",
    "aircraft_pitch_deg": "Aircraft Pitch (°)",
    "aircraft_roll_deg":  "Aircraft Roll (°)",
    "aircraft_yaw_deg":   "Aircraft Heading (°)",
    "gimbal_pitch_deg":   "Gimbal Pitch (°)",
    "gimbal_roll_deg":    "Gimbal Roll (°)",
    "gimbal_yaw_deg":     "Gimbal Heading (°)",
    "duration_s":         "Clip Length",
    "camera_model":       "Camera",
    "time_source":        "Clock Source",
    "indexed_file":       "Indexed Video",
    "relative_path":      "Path on Card",
    "sha256":             "SHA-256",
}

# Media telemetry source_type -> display text
SOURCE_TYPES = {"photo": "Photo", "video": "Video", "idx": "IDX record"}
# Media telemetry time_source prefix -> short display text
_TIME_SOURCES = (("photo EXIF", "Photo EXIF (camera clock)"),
                 ("video header", "Video header (camera clock)"),
                 ("IDX record", "IDX date (camera clock)"))

_DECIMALS = {
    "time_s": 2,
    "latitude": 7, "longitude": 7, "home_latitude": 7, "home_longitude": 7,
    "altitude_m": 1, "baro_alt_m": 1, "height_m": 1,
    "pitch_deg": 1, "roll_deg": 1, "yaw_deg": 1,
    "vel_n_ms": 2, "vel_e_ms": 2, "vel_d_ms": 2,
    "batt_volts": 2, "batt_amps": 2,
    "cell1_v": 3, "cell2_v": 3, "cell3_v": 3, "cell4_v": 3,
    "abs_altitude_m": 1, "rel_altitude_m": 1,
    "speed_x_ms": 1, "speed_y_ms": 1, "speed_z_ms": 1,
    "aircraft_pitch_deg": 1, "aircraft_roll_deg": 1, "aircraft_yaw_deg": 1,
    "gimbal_pitch_deg": 1, "gimbal_roll_deg": 1, "gimbal_yaw_deg": 1,
}
_INTEGERS = {"tick", "satnum", "batt_remcap_mah", "batt_percent", "batt_temp_c",
             "aileron", "elevator", "throttle", "rudder"}


def column_label(col: str) -> str:
    return COLUMN_LABELS.get(col) or col.replace("_", " ").title()


# Exports keep raw values, so columns whose on-screen text differs from the raw
# value get a header that says what the raw value is.
_EXPORT_LABELS = {
    "duration_s":      "Clip Length (s)",
    "flight_time_ms":  "Flight Time (ms)",
    "flyc_state":      "Flight Mode (code)",
    "connected_to_rc": "RC Connected (1=yes, 0=no)",
    "failure":         "Failure (code, 0=none)",
    "non_gps_error":   "GPS Status (code, 0=OK)",
}


def export_label(col: str) -> str:
    """Readable header for an exported (raw-valued) column."""
    return _EXPORT_LABELS.get(col) or column_label(col)


def to_number(v):
    """float(v), or None for blanks / non-numbers / NaN."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def format_duration(seconds: float) -> str:
    seconds = max(0.0, seconds)
    return f"{int(seconds // 60)}:{seconds % 60:04.1f}"


def format_value(col: str, raw) -> str:
    """Human-readable cell text for a raw CSV value."""
    if raw is None or raw == "":
        return ""
    if col == "source_type":
        return SOURCE_TYPES.get(str(raw), str(raw))
    if col == "sha256":
        return f"{raw[:16]}…" if len(str(raw)) > 16 else str(raw)
    if col == "time_source":
        for prefix, text in _TIME_SOURCES:
            if str(raw).startswith(prefix):
                return text
        return str(raw)
    v = to_number(raw)
    if v is None:
        return str(raw)
    if col == "flyc_state":
        return f"{FLIGHT_MODES.get(int(v), 'Unknown')} ({int(v)})"
    if col == "connected_to_rc":
        return "Yes" if int(v) == 1 else "No"
    if col == "failure":
        return "None" if int(v) == 0 else f"Code {int(v)}"
    if col == "non_gps_error":
        return GPS_STATUS.get(int(v), f"Code {int(v)}")
    if col == "flight_time_ms":
        return format_duration(v / 1000.0)
    if col == "duration_s":
        return format_duration(v)
    if col in _INTEGERS:
        return str(int(round(v)))
    if col in _DECIMALS:
        return f"{v:.{_DECIMALS[col]}f}"
    return str(raw)


def alert_level(rec_type: str, row: dict):
    """
    'alert' (red) for things an investigator must see, 'warn' (amber) for
    caution, else None.
    """
    n = lambda k: to_number(row.get(k))   # noqa: E731
    if rec_type == "FSTAT":
        if n("connected_to_rc") == 0 or (n("failure") or 0) != 0:
            return "alert"
        mode = n("flyc_state")
        if (n("non_gps_error") or 0) != 0 or (mode is not None and int(mode) in AUTO_RETURN_MODES):
            return "warn"
    elif rec_type == "BATTERY":
        pct, temp = n("batt_percent"), n("batt_temp_c")
        if (pct is not None and pct < 20) or (temp is not None and temp >= 60):
            return "alert"
        if pct is not None and pct < 30:
            return "warn"
    elif rec_type == "GPS":
        sats = n("satnum")
        if sats is not None and sats < 6:
            return "warn"
    return None


ALERT_LEGEND = ("Red = needs attention (RC signal lost, failure code, battery under 20% "
                "or over 60 °C).   Amber = caution (weak GPS, auto return / landing, "
                "battery under 30%).")
