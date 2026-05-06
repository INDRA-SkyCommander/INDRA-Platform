

import os
import datetime
import subprocess
import gzip
import shutil
from pathlib import Path

import requests

# ── Configuration ──────────────────────────────────────────────────────────────
NASA_USER = "kab00038"
NASA_PASS = "gb83VfWJu7%*^9PTrs2@"
HACKRF_BIN = "hackrf_transfer"
GPS_SIM_BIN = "./gps-sdr-sim"
WORKING_DIR = Path(__file__).resolve().parent

GPS_L1_FREQ = "1575420000"
SAMPLE_RATE = "2600000"


# ── Helpers ────────────────────────────────────────────────────────────────────
def find_matching_files(pattern: str) -> list[Path]:
    """Return every file in WORKING_DIR whose name contains *pattern*."""
    return [p for p in WORKING_DIR.iterdir() if pattern in p.name]


def clean_files(pattern: str) -> None:
    """Delete every file in WORKING_DIR whose name contains *pattern*."""
    for path in find_matching_files(pattern):
        try:
            path.unlink()
            print(f"[!] Removed old file: {path.name}")
        except OSError as e:
            print(f"[!] Error removing {path.name}: {e}")


# ── Date / Ephemeris ───────────────────────────────────────────────────────────
def get_gps_date_info() -> tuple[str, str, str]:
    """Return (YYYY, YY, DOY) for yesterday (ensures the file is published)."""
    yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
    return (
        yesterday.strftime("%Y"),
        yesterday.strftime("%y"),
        yesterday.strftime("%j"),
    )


def ephemeris_filename(yy: str, doy: str) -> str:
    """Build the uncompressed BRDC ephemeris filename."""
    return f"brdc{doy}0.{yy}n"


def local_ephemeris_exists(yy: str, doy: str) -> Path | None:
    """If today's ephemeris is already on disk, return its Path; else None."""
    target = WORKING_DIR / ephemeris_filename(yy, doy)
    return target if target.is_file() else None


def download_ephemeris(year: str, yy: str, doy: str) -> str | None:
    """Download & extract the BRDC ephemeris, skipping if it already exists."""
    existing = local_ephemeris_exists(yy, doy)
    if existing:
        print(f"[+] Ephemeris already exists: {existing.name} — skipping download.")
        return existing.name

    gz_name = f"{ephemeris_filename(yy, doy)}.gz"
    url = f"https://cddis.nasa.gov/archive/gnss/data/daily/{year}/brdc/{gz_name}"

    clean_files("brdc")

    print(f"[*] Downloading {gz_name} from cddis.nasa.gov...")
    with requests.Session() as session:
        session.auth = (NASA_USER, NASA_PASS)
        response = session.get(url, allow_redirects=True)

        # CDDIS may redirect through Earthdata login
        if response.history:
            response = session.get(response.url, auth=(NASA_USER, NASA_PASS))

        if response.status_code != 200 or response.text.startswith("<!DOCTYPE html>"):
            print("[!] Error: received HTML or auth failed.")
            print(
                "    Check your NASA credentials and ensure you have authorized "
                "the CDDIS application in Earthdata."
            )
            return None

        gz_path = WORKING_DIR / gz_name
        gz_path.write_bytes(response.content)
        print(f"[+] Downloaded {gz_name}")

    unzipped_name = ephemeris_filename(yy, doy)
    unzipped_path = WORKING_DIR / unzipped_name

    with gzip.open(gz_path, "rb") as f_in, open(unzipped_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

    gz_path.unlink()
    print(f"[+] Extracted to {unzipped_name}")
    return unzipped_name


# ── Simulation & Transmission ─────────────────────────────────────────────────
def run_sim(ephem_file: str, lat: str, lon: str, alt: str) -> None:
    """Generate the GPS baseband file with gps-sdr-sim."""
    clean_files("gpssim.bin")

    print(f"[*] Generating GPS signal file for {lat}, {lon}...")
    cmd = [
        GPS_SIM_BIN,
        "-e", ephem_file,
        "-l", f"{lat},{lon},{alt}",
        "-b", "8",
        "-d", "100",
    ]
    subprocess.run(cmd, check=True)


def transmit() -> None:
    """Prompt the user then transmit via HackRF."""
    choice = input("[?] Generation complete. Start transmitting? (y/n): ")
    if choice.strip().lower() != "y":
        print("[*] Transmission cancelled.")
        return

    power = input("Enter transmit power 0-47 (default 0): ").strip() or "0"
    print("[!] TRANSMITTING — press Ctrl+C to stop.")

    cmd = [
        HACKRF_BIN,
        "-t", "gpssim.bin",
        "-f", GPS_L1_FREQ,
        "-s", SAMPLE_RATE,
        "-a", "1",
        "-x", power,
    ]
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n[*] Transmission stopped.")


# ── Entry Point ────────────────────────────────────────────────────────────────
def main() -> None:
    year, yy, doy = get_gps_date_info()
    ephem = download_ephemeris(year, yy, doy)

    if not ephem:
        print("[!] Could not obtain ephemeris data. Exiting.")
        return

    lat = input("Enter Latitude  (e.g.  40.7128): ")
    lon = input("Enter Longitude (e.g. -74.0060): ")
    alt = input("Enter Altitude in metres: ")

    run_sim(ephem, lat, lon, alt)
    transmit()


if __name__ == "__main__":
    main()

