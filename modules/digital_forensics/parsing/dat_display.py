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
    "notes":              "Notes",
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


# One plain sentence per column: what it is, its unit, and where it comes from.
# Shown as a header tooltip and in the viewer's Details panel.
COLUMN_HELP = {
    # .DAT shared
    "time_s":          "Seconds since the first decoded record in this log (600 clock ticks = 1 s).",
    "tick":            "Raw flight-controller clock value from the log, kept for cross-checking.",
    # .DAT GPS
    "latitude":        "GPS latitude in decimal degrees (north is positive).",
    "longitude":       "GPS longitude in decimal degrees (east is positive, so the US is negative).",
    "altitude_m":      "GPS altitude in metres as the flight controller recorded it.",
    "baro_alt_m":      "Altitude from the barometer in metres; smoother than GPS altitude.",
    "pitch_deg":       "Nose up (+) or down (-) in degrees.",
    "roll_deg":        "Bank right (+) or left (-) in degrees.",
    "yaw_deg":         "Compass heading the nose points to, in degrees.",
    "vel_n_ms":        "Speed toward north in m/s (negative = moving south).",
    "vel_e_ms":        "Speed toward east in m/s (negative = moving west).",
    "vel_d_ms":        "Vertical speed in m/s, positive = descending.",
    "satnum":          "GPS satellites in use; under 6 means a weak position fix.",
    # .DAT flight status
    "height_m":        "Height above the takeoff point in metres.",
    "flyc_state":      "Flight-controller mode, e.g. P-GPS (normal), Go Home, Auto Landing.",
    "connected_to_rc": "Whether the aircraft could hear the remote controller.",
    "failure":         "Flight-controller failure code; anything but None needs a look.",
    "non_gps_error":   "Why GPS positioning was unavailable, or OK.",
    "flight_time_ms":  "Flight time the flight controller reported, as minutes:seconds.",
    # .DAT battery
    "batt_remcap_mah": "Charge left in the battery in milliamp-hours.",
    "batt_volts":      "Total battery pack voltage.",
    "batt_amps":       "Current drawn from the battery in amps.",
    "batt_percent":    "Battery charge left, in percent.",
    "batt_temp_c":     "Battery temperature in degrees Celsius.",
    "cell1_v":         "Voltage of battery cell 1; cells far apart point to a bad battery.",
    "cell2_v":         "Voltage of battery cell 2.",
    "cell3_v":         "Voltage of battery cell 3.",
    "cell4_v":         "Voltage of battery cell 4.",
    # .DAT RC
    "aileron":         "Right stick left/right (roll), in raw stick units.",
    "elevator":        "Right stick forward/back (pitch), in raw stick units.",
    "throttle":        "Left stick up/down (climb/descend), in raw stick units.",
    "rudder":          "Left stick left/right (turn), in raw stick units.",
    # .DAT home point
    "home_latitude":   "Latitude the aircraft recorded as home (where Go Home returns to).",
    "home_longitude":  "Longitude the aircraft recorded as home.",
    # Media telemetry
    "timestamp":          "When the photo was taken or the recording started, on the drone's camera clock (not adjusted for time zone).",
    "source_type":        "Where this point came from: a photo's metadata, a video's header, or a MISC/IDX index record on the card.",
    "source_file":        "The photo, video or index file the values were read from.",
    "abs_altitude_m":     "Height above sea level in metres, from the photo's GPS/XMP data. Videos do not record it, so it is blank for them.",
    "rel_altitude_m":     "Height above the takeoff point in metres (barometer). 0.0 means the drone was on the ground.",
    "speed_x_ms":         "Aircraft speed along DJI's X axis in m/s, as the camera recorded it (axis convention not yet confirmed).",
    "speed_y_ms":         "Aircraft speed along DJI's Y axis in m/s, as the camera recorded it (axis convention not yet confirmed).",
    "speed_z_ms":         "Aircraft vertical speed along DJI's Z axis in m/s (axis convention not yet confirmed).",
    "aircraft_pitch_deg": "Aircraft nose up (+) or down (-) in degrees when the shot was taken.",
    "aircraft_roll_deg":  "Aircraft bank in degrees when the shot was taken.",
    "aircraft_yaw_deg":   "Compass heading the aircraft faced, in degrees.",
    "gimbal_pitch_deg":   "Camera tilt in degrees: 0 = level, -90 = straight down.",
    "gimbal_roll_deg":    "Camera roll in degrees.",
    "gimbal_yaw_deg":     "Compass heading the camera faced, in degrees.",
    "duration_s":         "Length of the video clip (minutes:seconds).",
    "camera_model":       "Camera model from the file's metadata (FC330 = Phantom 4).",
    "time_source":        "Which clock the time came from: photo EXIF, video header or IDX date.",
    "indexed_file":       "The video an IDX record points to. If that video is not on the card, it was deleted or moved.",
    "relative_path":      "Where the file sits on the SD card.",
    "sha256":             "SHA-256 hash of the source file (full value in the Details panel and in exports).",
    "notes":              "Cross-checks: an IDX record that repeats a video on the card, or one whose video is missing.",
}


def column_help(col: str) -> str:
    return COLUMN_HELP.get(col, "")


# One line under each tab name saying what the tab is.
TAB_HELP = {
    "GPS":     "Position, altitude, attitude and speed from the flight controller, about 2 per second.",
    "FSTAT":   "Flight-controller status once a second: mode, RC link, failures, flight time.",
    "BATTERY": "Battery charge, voltage, current and temperature every few seconds.",
    "RC":      "What the pilot did with the sticks on the remote controller.",
    "HOME":    "The home point Go Home returns to.",
    "MEDIA":   "One row per photo, video or IDX record: where and how the drone was when it was "
               "taken. These are snapshots, not a continuous flight path.",
}

# Columns never hidden by "hide empty / all-zero columns".
# Status columns stay too: "no failures" / "RC connected" is itself a finding.
KEY_COLUMNS = {"time_s", "timestamp", "source_type", "source_file", "latitude", "longitude",
               "home_latitude", "home_longitude",
               "flyc_state", "connected_to_rc", "failure", "non_gps_error"}


def is_uninformative(rows, col: str) -> bool:
    """True when every value in the column is blank or numerically zero."""
    if col in KEY_COLUMNS:
        return False
    for r in rows:
        raw = r.get(col)
        if raw in (None, ""):
            continue
        v = to_number(raw)
        if v is None or v != 0:
            return False
    return True


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
