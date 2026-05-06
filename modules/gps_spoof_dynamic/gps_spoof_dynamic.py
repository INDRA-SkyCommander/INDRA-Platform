"""
GPS spoofing module for INDRA Platform.

Supports both:
 - Dynamic mode with trajectory CSV input (`-u` or `-x`)
 - Auto-generated straight flight path CSV from start Lat/Lon/Alt
"""

STANDALONE = True

import os
import sys
import json
import math
import datetime
import subprocess
import gzip
import shutil
from pathlib import Path

import requests


_MODULE_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _MODULE_DIR.parent.parent
_DATA_DIR = _PROJECT_ROOT / "data"
_TARGET_DATA_FILE = _DATA_DIR / "module_input_data.json"
_GPS_SDR_SIM_DIR = _PROJECT_ROOT / "gps-sdr-sim"

NASA_USER = "YOUR_NASA_USER"
NASA_PASS = "YOUR_NASA_PASS"

HACKRF_BIN = "hackrf_transfer"
GPS_SIM_BIN = _GPS_SDR_SIM_DIR / "gps-sdr-sim"
WORKING_DIR = _GPS_SDR_SIM_DIR

GPS_L1_FREQ = "1575420000"
SAMPLE_RATE = "2600000"
GENERATED_PATH_META = WORKING_DIR / "generated_straight_path_meta.json"
GENERATED_PATH_CSV = WORKING_DIR / "generated_straight_path.csv"

WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)
EARTH_RADIUS_M = 6378137.0


def find_matching_files(pattern: str) -> list:
    return [path for path in WORKING_DIR.iterdir() if pattern in path.name]


def clean_files(pattern: str) -> None:
    for path in find_matching_files(pattern):
        try:
            path.unlink()
            print(f"[!] Removed old file: {path.name}")
        except OSError as error:
            print(f"[!] Error removing {path.name}: {error}")


def get_gps_date_info() -> tuple:
    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
    return (
        yesterday.strftime("%Y"),
        yesterday.strftime("%y"),
        yesterday.strftime("%j"),
    )


def ephemeris_filename(yy: str, doy: str) -> str:
    return f"brdc{doy}0.{yy}n"


def local_ephemeris_exists(yy: str, doy: str):
    target = WORKING_DIR / ephemeris_filename(yy, doy)
    return target if target.is_file() else None


def _validate_runtime_paths() -> bool:
    if not WORKING_DIR.is_dir():
        print(f"[!] gps-sdr-sim directory not found: {WORKING_DIR}")
        return False

    if not GPS_SIM_BIN.is_file():
        print(f"[!] gps-sdr-sim binary not found: {GPS_SIM_BIN}")
        print("    Build it from the INDRA root with:")
        print("    cd gps-sdr-sim && make")
        return False

    return True


def download_ephemeris(year: str, yy: str, doy: str):
    existing = local_ephemeris_exists(yy, doy)
    if existing:
        print(f"[+] Ephemeris already exists: {existing.name} — skipping download.")
        return existing.name

    if not NASA_USER or not NASA_PASS:
        print("[!] NASA_USER / NASA_PASS environment variables are not set.")
        return None

    gz_name = f"{ephemeris_filename(yy, doy)}.gz"
    url = f"https://cddis.nasa.gov/archive/gnss/data/daily/{year}/brdc/{gz_name}"

    clean_files("brdc")

    print(f"[*] Downloading {gz_name} from cddis.nasa.gov...")
    with requests.Session() as session:
        session.auth = (NASA_USER, NASA_PASS)
        response = session.get(url, allow_redirects=True)

        if response.history:
            response = session.get(response.url, auth=(NASA_USER, NASA_PASS))

        if response.status_code != 200 or response.text.startswith("<!DOCTYPE html>"):
            print("[!] Error: received HTML or auth failed.")
            return None

        gz_path = WORKING_DIR / gz_name
        gz_path.write_bytes(response.content)
        print(f"[+] Downloaded {gz_name}")

    unzipped_name = ephemeris_filename(yy, doy)
    unzipped_path = WORKING_DIR / unzipped_name

    with gzip.open(gz_path, "rb") as source, open(unzipped_path, "wb") as destination:
        shutil.copyfileobj(source, destination)

    gz_path.unlink()
    print(f"[+] Extracted to {unzipped_name}")
    return unzipped_name


def _detect_motion_flag(csv_path: Path) -> str:
    """
    Returns the appropriate gps-sdr-sim motion option:
      -x for LLH files (time,lat,lon,height)
      -u for ECEF files (time,x,y,z)
    """
    with open(csv_path, "r") as csv_file:
        for raw_line in csv_file:
            line = raw_line.strip()
            if not line:
                continue

            parts = [token.strip() for token in line.split(",")]
            if len(parts) < 4:
                raise ValueError("CSV rows must have at least 4 comma-separated values")

            second = float(parts[1])
            third = float(parts[2])
            if -90.0 <= second <= 90.0 and -180.0 <= third <= 180.0:
                return "-x"
            return "-u"

    raise ValueError("CSV file is empty")


def run_sim_csv(ephem_file: str, csv_file: str) -> int:
    clean_files("gpssim.bin")

    csv_path = Path(csv_file).expanduser().resolve()
    if not csv_path.is_file():
        print(f"[!] Trajectory CSV not found: {csv_path}")
        return 1

    try:
        motion_flag = _detect_motion_flag(csv_path)
    except Exception as error:
        print(f"[!] Invalid trajectory CSV: {error}")
        return 1

    mode = "LLH (-x)" if motion_flag == "-x" else "ECEF (-u)"
    print(f"[*] Generating dynamic GPS signal from CSV ({mode}): {csv_path}")

    command = [
        str(GPS_SIM_BIN),
        "-e", ephem_file,
        motion_flag, str(csv_path),
        "-b", "8",
        "-d", "100",
    ]

    process = subprocess.Popen(
        command,
        cwd=str(WORKING_DIR),
        stderr=subprocess.PIPE,
        bufsize=0,
    )

    buffer = b""
    while True:
        byte = process.stderr.read(1)
        if not byte:
            break
        if byte in (b"\r", b"\n"):
            text = buffer.decode("utf-8", errors="replace").strip()
            if text:
                end = "\r" if byte == b"\r" else "\n"
                sys.stderr.write(text + end)
                sys.stderr.flush()
            buffer = b""
        else:
            buffer += byte

    remaining = buffer.decode("utf-8", errors="replace").strip()
    if remaining:
        sys.stderr.write(remaining + "\n")
        sys.stderr.flush()

    process.wait()
    return process.returncode


def run_sim_static(ephem_file: str, lat: str, lon: str, alt: str) -> int:
    clean_files("gpssim.bin")

    print(f"[*] Generating static GPS signal for {lat}, {lon}, alt {alt}m ...")
    command = [
        str(GPS_SIM_BIN),
        "-e", ephem_file,
        "-l", f"{lat},{lon},{alt}",
        "-b", "8",
        "-d", "100",
    ]

    process = subprocess.Popen(
        command,
        cwd=str(WORKING_DIR),
        stderr=subprocess.PIPE,
        bufsize=0,
    )

    buffer = b""
    while True:
        byte = process.stderr.read(1)
        if not byte:
            break
        if byte in (b"\r", b"\n"):
            text = buffer.decode("utf-8", errors="replace").strip()
            if text:
                end = "\r" if byte == b"\r" else "\n"
                sys.stderr.write(text + end)
                sys.stderr.flush()
            buffer = b""
        else:
            buffer += byte

    remaining = buffer.decode("utf-8", errors="replace").strip()
    if remaining:
        sys.stderr.write(remaining + "\n")
        sys.stderr.flush()

    process.wait()
    return process.returncode


def _lat_lon_alt_to_ecef(lat_deg: float, lon_deg: float, alt_m: float):
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)

    sin_lat = math.sin(lat)
    cos_lat = math.cos(lat)
    sin_lon = math.sin(lon)
    cos_lon = math.cos(lon)

    n = WGS84_A / math.sqrt(1.0 - WGS84_E2 * sin_lat * sin_lat)

    x = (n + alt_m) * cos_lat * cos_lon
    y = (n + alt_m) * cos_lat * sin_lon
    z = (n * (1.0 - WGS84_E2) + alt_m) * sin_lat
    return x, y, z


def _destination_point(lat_deg: float, lon_deg: float, bearing_deg: float, distance_m: float):
    lat1 = math.radians(lat_deg)
    lon1 = math.radians(lon_deg)
    brng = math.radians(bearing_deg)

    angular_distance = distance_m / EARTH_RADIUS_M

    sin_lat1 = math.sin(lat1)
    cos_lat1 = math.cos(lat1)
    sin_ad = math.sin(angular_distance)
    cos_ad = math.cos(angular_distance)

    lat2 = math.asin(sin_lat1 * cos_ad + cos_lat1 * sin_ad * math.cos(brng))
    lon2 = lon1 + math.atan2(
        math.sin(brng) * sin_ad * cos_lat1,
        cos_ad - sin_lat1 * math.sin(lat2),
    )

    lon2 = (lon2 + math.pi) % (2.0 * math.pi) - math.pi

    return math.degrees(lat2), math.degrees(lon2)


def generate_straight_path_csv(lat: str, lon: str, alt: str, module_cfg: dict) -> str | None:
    """
    Generates a straight-flight trajectory CSV from start coordinates.

    Optional config keys:
      - path_speed_mps (default 3.0)
      - path_heading_deg (default 45.0)
      - path_duration_s (default 300.0)
      - path_sample_hz (default 10.0)
      - path_climb_rate_mps (default 0.0)
    """
    output_path = GENERATED_PATH_CSV

    try:
        start_lat = float(lat)
        start_lon = float(lon)
        start_alt = float(alt)
        speed_mps = float(module_cfg.get("path_speed_mps", 3.0))
        heading_deg = float(module_cfg.get("path_heading_deg", 45.0))
        duration_s = float(module_cfg.get("path_duration_s", 300.0))
        sample_hz = float(module_cfg.get("path_sample_hz", 10.0))
        climb_mps = float(module_cfg.get("path_climb_rate_mps", 0.0))
    except (TypeError, ValueError) as error:
        print(f"[!] Invalid straight-path parameters: {error}")
        return None

    if sample_hz <= 0:
        print("[!] path_sample_hz must be > 0")
        return None
    if duration_s < 0:
        print("[!] path_duration_s must be >= 0")
        return None

    dt = 1.0 / sample_hz
    total_samples = int(round(duration_s * sample_hz)) + 1

    print("[*] No CSV provided. Generating straight flight path from start coordinates...")
    try:
        with open(output_path, "w") as output_file:
            for i in range(total_samples):
                t = i * dt
                distance = speed_mps * t
                altitude = start_alt + climb_mps * t
                point_lat, point_lon = _destination_point(start_lat, start_lon, heading_deg, distance)
                x, y, z = _lat_lon_alt_to_ecef(point_lat, point_lon, altitude)
                output_file.write(f"{t:5.1f},{x:12.3f}, {y:12.3f}, {z:12.3f}\n")
    except Exception as error:
        print(f"[!] Straight path generation failed: {error}")
        return None

    if not output_path.is_file():
        print(f"[!] Expected generated CSV not found: {output_path}")
        return None

    return str(output_path)


def _start_coordinates_changed(lat: str, lon: str, alt: str) -> bool:
    """
    Returns True when start coordinates differ from the last generated-path run.
    """
    try:
        lat_now = float(lat)
        lon_now = float(lon)
        alt_now = float(alt)
    except (TypeError, ValueError):
        return True

    if not GENERATED_PATH_META.is_file():
        return True

    try:
        with open(GENERATED_PATH_META, "r") as meta_file:
            meta = json.load(meta_file)

        lat_prev = float(meta.get("latitude"))
        lon_prev = float(meta.get("longitude"))
        alt_prev = float(meta.get("altitude"))
    except Exception:
        return True

    coord_epsilon = 1e-7
    alt_epsilon = 1e-3

    return (
        abs(lat_now - lat_prev) > coord_epsilon
        or abs(lon_now - lon_prev) > coord_epsilon
        or abs(alt_now - alt_prev) > alt_epsilon
    )


def _save_start_coordinates(lat: str, lon: str, alt: str) -> None:
    try:
        with open(GENERATED_PATH_META, "w") as meta_file:
            json.dump(
                {
                    "latitude": float(lat),
                    "longitude": float(lon),
                    "altitude": float(alt),
                },
                meta_file,
                indent=2,
            )
    except Exception as error:
        print(f"[!] Warning: could not save generated-path metadata: {error}")


def transmit(power: str = "1") -> int:
    bin_path = WORKING_DIR / "gpssim.bin"
    if not bin_path.is_file():
        print("[!] gpssim.bin not found — run simulation first.")
        return 1

    print(f"[!] TRANSMITTING at power level {power} — module will run until stopped.")
    command = [
        HACKRF_BIN,
        "-t", str(bin_path),
        "-f", GPS_L1_FREQ,
        "-s", SAMPLE_RATE,
        "-a", "1",
        "-x", power,
    ]
    try:
        result = subprocess.run(command)
        return result.returncode
    except KeyboardInterrupt:
        print("\n[*] Transmission stopped.")
        return 0


def main() -> int:
    if not _TARGET_DATA_FILE.is_file():
        print(f"[!] Config file not found: {_TARGET_DATA_FILE}")
        return 1

    if not _validate_runtime_paths():
        return 1

    with open(_TARGET_DATA_FILE, "r") as config_file:
        config = json.load(config_file)

    module_cfg = config.get("gps_spoof_dynamic", {})
    csv_file = module_cfg.get("csv_file", "")
    lat = module_cfg.get("latitude", "")
    lon = module_cfg.get("longitude", "")
    alt = module_cfg.get("altitude", "100")
    power = module_cfg.get("tx_power", "0")

    year, yy, doy = get_gps_date_info()
    ephemeris = download_ephemeris(year, yy, doy)
    if not ephemeris:
        print("[!] Could not obtain ephemeris data. Exiting.")
        return 1

    if csv_file:
        sim_rc = run_sim_csv(ephemeris, csv_file)
    else:
        if not lat or not lon:
            print("[!] Either csv_file or latitude/longitude is required in gps_spoof_dynamic config.")
            return 1

        if _start_coordinates_changed(lat, lon, alt):
            generated_csv = generate_straight_path_csv(lat, lon, alt, module_cfg)
            if not generated_csv:
                return 1
            _save_start_coordinates(lat, lon, alt)
            sim_rc = run_sim_csv(ephemeris, generated_csv)
        else:
            if GENERATED_PATH_CSV.is_file():
                print("[*] Start coordinates unchanged; reusing existing generated flight path CSV.")
                sim_rc = run_sim_csv(ephemeris, str(GENERATED_PATH_CSV))
            else:
                print("[*] Start coordinates unchanged, but generated CSV is missing. Regenerating once.")
                generated_csv = generate_straight_path_csv(lat, lon, alt, module_cfg)
                if not generated_csv:
                    return 1
                _save_start_coordinates(lat, lon, alt)
                sim_rc = run_sim_csv(ephemeris, generated_csv)

    if sim_rc != 0:
        print(f"[!] gps-sdr-sim exited with code {sim_rc}")
        return sim_rc

    return transmit(power)


if __name__ == "__main__":
    sys.exit(main())
