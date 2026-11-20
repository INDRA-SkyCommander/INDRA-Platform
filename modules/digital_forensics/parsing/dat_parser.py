"""
DJI Phantom 3 binary .dat flight log parser.

File structure (confirmed from reverse engineering DROP / DatCon source):
    128-byte file header; bytes 16-20 are ASCII "BUILD"
    Sequential binary records:
        [0x55][pktlen: uint8][padding: uint8 = 0x00]
        [type: uint8][subtype: uint8][msg: uint8][tickNo: uint32-LE]
        [payload: pktlen-10 bytes, XOR-decoded with tickNo % 256]

    pktlen is the total packet size (including the leading 0x55 byte).
    The next packet starts at pos + pktlen.
"""

import csv
import math
import struct


FILE_HEADER_SIZE = 128
_BUILD_MAGIC     = b"BUILD"

# Phantom 3 flight-controller clock: DatCon converts tickNo to seconds at 600/s.
TICKS_PER_SECOND = 600.0

# Record type/subtype pairs
_GPS   = (0xCF, 0x01)   # GPS + IMU: lat/lon/alt/quaternion attitude
_FSTAT = (0x2A, 0x0C)   # Flight status: lat/lon/height/attitude/state
_HP    = (0xC6, 0x0D)   # Home point GPS coordinates
_RC    = (0x98, 0x00)   # Remote control stick inputs
_BATT  = (0x44, 0x11)   # Advanced battery: volts/current/capacity/temp


def _xor_decode(raw: bytes, tick_no: int) -> bytes:
    key = tick_no % 256
    return bytes(b ^ key for b in raw)


def _quat_to_euler_deg(qw, qx, qy, qz):
    """Return (pitch_deg, roll_deg, yaw_deg) from quaternion (w, x, y, z)."""
    unit = qw*qw + qx*qx + qy*qy + qz*qz
    if unit == 0:
        return 0.0, 0.0, 0.0
    test = qw*qx + qy*qz
    if test > 0.499 * unit:
        return math.degrees(math.pi / 2), 0.0, math.degrees(2.0 * math.atan2(qy, qw))
    if test < -0.499 * unit:
        return math.degrees(-math.pi / 2), 0.0, math.degrees(-2.0 * math.atan2(qy, qw))
    yaw   = math.atan2(2.0*(qw*qz - qx*qy), 1.0 - 2.0*(qz*qz + qx*qx))
    roll  = math.asin(max(-1.0, min(1.0, 2.0 * test / unit)))
    pitch = math.atan2(2.0*(qw*qy - qx*qz), 1.0 - 2.0*(qy*qy + qx*qx))
    return math.degrees(pitch), math.degrees(roll), math.degrees(yaw)


def _parse_gps(p: bytes) -> dict:
    """
    GPS/IMU record — primary lat/lon/altitude source.

    Offsets (decoded payload):
        0   : longitude  double  radians
        8   : latitude   double  radians
        16  : altitude   float   metres
        20  : accelX     float
        24  : accelY     float
        28  : accelZ     float
        32  : gyroX      float
        36  : gyroY      float
        40  : gyroZ      float
        44  : baroAlt    float   metres
        48  : quatW      float
        52  : quatX      float
        56  : quatY      float
        60  : quatZ      float
        76  : velN       float   m/s north
        80  : velE       float   m/s east
        84  : velD       float   m/s down
        100 : magX       int16
        102 : magY       int16
        104 : magZ       int16
        106 : imuTemp    int16
        116 : satnum     uint8
    """
    if len(p) < 117:
        return {}
    lon_r, lat_r = struct.unpack_from('<dd', p, 0)
    lat = round(math.degrees(lat_r), 7)
    lon = round(math.degrees(lon_r), 7)
    alt_m   = struct.unpack_from('<f', p, 16)[0]
    baro_m  = struct.unpack_from('<f', p, 44)[0]
    qw, qx, qy, qz = struct.unpack_from('<ffff', p, 48)
    pitch, roll, yaw = _quat_to_euler_deg(qw, qx, qy, qz)
    vel_n, vel_e, vel_d = struct.unpack_from('<fff', p, 76)
    satnum  = p[116]

    # Clear coordinates when no valid GPS fix
    if lat == 0 or lon == 0 or abs(lat) <= 1.0 or abs(lon) <= 1.0 or satnum <= 2 or satnum >= 32:
        lat = lon = None

    return {
        'rec_type':   'GPS',
        'latitude':   lat,
        'longitude':  lon,
        'altitude_m': round(alt_m, 2),
        'baro_alt_m': round(baro_m, 2),
        'pitch_deg':  round(pitch, 2),
        'roll_deg':   round(roll, 2),
        'yaw_deg':    round(yaw, 2),
        'vel_n_ms':   round(vel_n, 3),
        'vel_e_ms':   round(vel_e, 3),
        'vel_d_ms':   round(vel_d, 3),
        'satnum':     satnum,
    }


def _parse_fstat(p: bytes) -> dict:
    """
    Flight status record — attitude, state, flight time.

    Offsets (decoded payload):
        0   : longitude      double  radians
        8   : latitude       double  radians
        16  : height         int16   / 10.0  metres AGL
        24  : pitch          int16   / 10.0  degrees
        26  : roll           int16   / 10.0  degrees
        28  : yaw            int16   / 10.0  degrees
        30  : flags          byte    bits 0-6 = flyc_state, bit 7 = NOT connected to RC
        38  : failure        uint8
        39  : nonGPSError    uint8   bits 0-2
        42  : flight_time    int16   × 100 ms
    """
    if len(p) < 44:
        return {}
    lon_r, lat_r = struct.unpack_from('<dd', p, 0)
    height  = struct.unpack_from('<h', p, 16)[0] / 10.0
    pitch   = struct.unpack_from('<h', p, 24)[0] / 10.0
    roll    = struct.unpack_from('<h', p, 26)[0] / 10.0
    yaw     = struct.unpack_from('<h', p, 28)[0] / 10.0
    b30     = p[30]
    ft_ms   = struct.unpack_from('<h', p, 42)[0] * 100
    return {
        'rec_type':        'FSTAT',
        'latitude':        round(math.degrees(lat_r), 7),
        'longitude':       round(math.degrees(lon_r), 7),
        'height_m':        height,
        'pitch_deg':       pitch,
        'roll_deg':        roll,
        'yaw_deg':         yaw,
        'flyc_state':      b30 & 0x7F,
        'connected_to_rc': int((b30 & 0x80) == 0),
        'failure':         p[38],
        'non_gps_error':   p[39] & 0x07,
        'flight_time_ms':  ft_ms,
    }


def _parse_home(p: bytes) -> dict:
    """HomePoint — home GPS coordinates."""
    if len(p) < 16:
        return {}
    lon_r, lat_r = struct.unpack_from('<dd', p, 0)
    return {
        'rec_type':      'HOME',
        'home_latitude':  round(math.degrees(lat_r), 7),
        'home_longitude': round(math.degrees(lon_r), 7),
    }


def _parse_rc(p: bytes) -> dict:
    """RC sticks — aileron / elevator / throttle / rudder."""
    if len(p) < 12:
        return {}
    return {
        'rec_type': 'RC',
        'aileron':  struct.unpack_from('<h', p, 4)[0],
        'elevator': struct.unpack_from('<h', p, 6)[0],
        'throttle': struct.unpack_from('<h', p, 8)[0],
        'rudder':   struct.unpack_from('<h', p, 10)[0],
    }


def _parse_battery(p: bytes) -> dict:
    """
    Advanced battery record.

    Offsets (decoded payload):
        2   : ratedCapacity    int16   mAh
        4   : remainingCap     int16   mAh
        6   : totalVolts       int16   / 1000.0  V
        8   : current          uint16  (65536 - value) / 1000.0  A (positive = discharge)
        11  : percentCapacity  uint8   0-100 %
        12  : battTemp         uint8   °C
        18  : volt1            int16   / 1000.0  V
        20  : volt2            int16   / 1000.0  V
        22  : volt3            int16   / 1000.0  V
        24  : volt4            int16   / 1000.0  V
    """
    if len(p) < 26:
        return {}
    rem_cap = struct.unpack_from('<h', p, 4)[0]
    volts   = struct.unpack_from('<h', p, 6)[0] / 1000.0
    raw_i   = struct.unpack_from('<H', p, 8)[0]
    amps    = (65536 - raw_i) / 1000.0
    pct     = p[11]
    temp_c  = p[12]
    v1, v2, v3, v4 = [struct.unpack_from('<h', p, 18 + i*2)[0] / 1000.0 for i in range(4)]
    return {
        'rec_type':        'BATTERY',
        'batt_remcap_mah': rem_cap,
        'batt_volts':      round(volts, 3),
        'batt_amps':       round(amps, 3),
        'batt_percent':    pct,
        'batt_temp_c':     temp_c,
        'cell1_v':         round(v1, 3),
        'cell2_v':         round(v2, 3),
        'cell3_v':         round(v3, 3),
        'cell4_v':         round(v4, 3),
    }


_PARSERS = {
    _GPS:   _parse_gps,
    _FSTAT: _parse_fstat,
    _HP:    _parse_home,
    _RC:    _parse_rc,
    _BATT:  _parse_battery,
}


def parse_dat(dat_path: str, csv_path: str) -> dict:
    """
    Parse a DJI Phantom 3 .dat binary flight log and write a CSV.

    Args:
        dat_path : path to the input .dat file
        csv_path : where to write the output CSV

    Returns:
        {
          "records_total":   int,  # all structurally valid records
          "records_parsed":  int,  # records with a known type that produced a row
          "checksum_errors": int,  # bytes skipped while seeking a valid start
          "header_skip":     int,  # always FILE_HEADER_SIZE for valid files
          "row_count":       int,
          "csv_path":        str | None,
        }
    """
    with open(dat_path, 'rb') as f:
        data = f.read()

    if len(data) < FILE_HEADER_SIZE or data[16:21] != _BUILD_MAGIC:
        got = data[16:21] if len(data) >= 21 else data[:min(len(data), 5)]
        return {
            "records_total": 0, "records_parsed": 0, "checksum_errors": 0,
            "header_skip": 0, "row_count": 0, "csv_path": None,
            "error": f"Not a DJI .dat file (expected b'BUILD' at byte 16, got {got!r})",
        }

    pos     = FILE_HEADER_SIZE
    rows    = []
    first_tick = None
    total   = 0
    parsed  = 0
    skipped = 0

    while pos < len(data) - 10:
        if data[pos] != 0x55:
            pos += 1
            skipped += 1
            continue

        pktlen  = data[pos + 1]
        padding = data[pos + 2]

        if padding != 0x00 or pktlen < 10 or pos + pktlen > len(data):
            pos += 1
            skipped += 1
            continue

        # Validate by checking that the next packet boundary starts with 0x55
        next_pos = pos + pktlen
        if next_pos < len(data) and data[next_pos] != 0x55:
            pos += 1
            skipped += 1
            continue

        ptype    = data[pos + 3]
        psubtype = data[pos + 4]
        tick_no  = struct.unpack_from('<I', data, pos + 6)[0]

        raw_payload = data[pos + 10: pos + pktlen]
        payload     = _xor_decode(raw_payload, tick_no)

        total += 1
        parser = _PARSERS.get((ptype, psubtype))
        if parser:
            row = parser(payload)
            if row:
                if first_tick is None:
                    first_tick = tick_no
                # time_s: seconds since the first decoded record; tick: raw clock value
                row = {"rec_type": row.pop("rec_type"),
                       "time_s":   round((tick_no - first_tick) / TICKS_PER_SECOND, 3),
                       "tick":     tick_no,
                       **row}
                rows.append(row)
                parsed += 1

        pos = next_pos

    csv_out = None
    if rows:
        all_keys: list = []
        seen: set = set()
        for r in rows:
            for k in r:
                if k not in seen:
                    all_keys.append(k)
                    seen.add(k)
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(rows)
        csv_out = csv_path

    return {
        "records_total":   total,
        "records_parsed":  parsed,
        "checksum_errors": skipped,
        "header_skip":     FILE_HEADER_SIZE,
        "row_count":       len(rows),
        "csv_path":        csv_out,
    }


# ── Flight summary (used by the Forensics-tab CSV viewer) ─────────────────────

def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _haversine_m(lat1, lon1, lat2, lon2):
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def summarize_dat_rows(rows: list) -> dict:
    """
    Summarise decoded .dat rows (dicts as read back from the CSV by DictReader).

    Returns a dict of raw values; any metric without data is None:
        counts, flight_time_s, max_alt_m, max_speed_ms, home, start, end,
        distance_m, max_from_home_m, batt_start_pct, batt_end_pct,
        batt_min_v, batt_max_temp_c, sats_min, sats_max,
        rc_lost_records, failure_records, flight_modes
    """
    by_type: dict = {}
    for r in rows:
        by_type.setdefault(r.get("rec_type") or "UNKNOWN", []).append(r)
    gps   = by_type.get("GPS", [])
    fstat = by_type.get("FSTAT", [])
    batt  = by_type.get("BATTERY", [])
    home  = by_type.get("HOME", [])

    def col(rs, key):
        return [x for x in (_num(r.get(key)) for r in rs) if x is not None]

    def _max(vals):
        return max(vals) if vals else None

    ft = col(fstat, "flight_time_ms")
    alts = col(gps, "altitude_m") or col(fstat, "height_m")
    speeds = []
    for r in gps:
        vn, ve = _num(r.get("vel_n_ms")), _num(r.get("vel_e_ms"))
        if vn is not None and ve is not None:
            speeds.append(math.hypot(vn, ve))

    track = []
    for r in gps:
        lat, lon = _num(r.get("latitude")), _num(r.get("longitude"))
        if lat is not None and lon is not None and (not track or track[-1] != (lat, lon)):
            track.append((lat, lon))
    distance = sum(_haversine_m(*a, *b) for a, b in zip(track, track[1:])) if track else None

    home_pt = None
    for r in home:
        lat, lon = _num(r.get("home_latitude")), _num(r.get("home_longitude"))
        if lat is not None and lon is not None:
            home_pt = (lat, lon)
            break
    ref = home_pt or (track[0] if track else None)
    from_home = _max([_haversine_m(*ref, *p) for p in track]) if ref and track else None

    pct = col(batt, "batt_percent")
    sats = col(gps, "satnum")
    rc_flags = col(fstat, "connected_to_rc")
    modes = []
    for m in col(fstat, "flyc_state"):
        if int(m) not in modes:
            modes.append(int(m))
    failures = col(fstat, "failure")

    return {
        "counts":          {k: len(v) for k, v in by_type.items()},
        "flight_time_s":   (_max(ft) / 1000.0) if ft else None,
        "max_alt_m":       _max(alts),
        "max_speed_ms":    _max(speeds),
        "home":            home_pt,
        "start":           track[0] if track else None,
        "end":             track[-1] if track else None,
        "distance_m":      distance,
        "max_from_home_m": from_home,
        "batt_start_pct":  pct[0] if pct else None,
        "batt_end_pct":    pct[-1] if pct else None,
        "batt_min_v":      min(col(batt, "batt_volts")) if col(batt, "batt_volts") else None,
        "batt_max_temp_c": _max(col(batt, "batt_temp_c")),
        "sats_min":        int(min(sats)) if sats else None,
        "sats_max":        int(max(sats)) if sats else None,
        "rc_lost_records": sum(1 for x in rc_flags if x == 0) if rc_flags else None,
        "failure_records": sum(1 for x in failures if x != 0) if failures else None,
        "flight_modes":    modes,           # flyc_state codes, in order first seen
    }
