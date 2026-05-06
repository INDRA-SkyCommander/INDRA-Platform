#!/usr/bin/env python3
"""
Generate a straight-line flight path CSV for gps-sdr-sim dynamic ECEF mode (-u).

Output format matches files like circle.csv:
  time_seconds,ecef_x,ecef_y,ecef_z

Example:
  python3 generate_straight_flight_path.py \
    --lat 40.7128 --lon -74.0060 --alt 100 \
    --speed 3.0 --heading 60 --duration 300 \
    --output straight_path.csv
"""

import argparse
import math

WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)
EARTH_RADIUS_M = 6378137.0


def lat_lon_alt_to_ecef(lat_deg: float, lon_deg: float, alt_m: float):
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


def destination_point(lat_deg: float, lon_deg: float, bearing_deg: float, distance_m: float):
    """
    Move from start point along a constant bearing over the Earth surface.
    Uses a spherical approximation for path stepping.
    """
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


def generate_path(
    start_lat: float,
    start_lon: float,
    start_alt: float,
    speed_mps: float,
    heading_deg: float,
    duration_s: float,
    sample_hz: float,
    climb_mps: float,
):
    dt = 1.0 / sample_hz
    total_samples = int(round(duration_s * sample_hz)) + 1

    rows = []
    for i in range(total_samples):
        t = i * dt
        distance = speed_mps * t
        alt = start_alt + climb_mps * t

        lat, lon = destination_point(start_lat, start_lon, heading_deg, distance)
        x, y, z = lat_lon_alt_to_ecef(lat, lon, alt)
        rows.append((t, x, y, z))

    return rows


def main():
    parser = argparse.ArgumentParser(
        description="Generate a straight-line ECEF trajectory CSV for gps-sdr-sim -u"
    )
    parser.add_argument("--lat", type=float, required=True, help="Start latitude (degrees)")
    parser.add_argument("--lon", type=float, required=True, help="Start longitude (degrees)")
    parser.add_argument("--alt", type=float, default=100.0, help="Start altitude (meters)")
    parser.add_argument(
        "--speed",
        type=float,
        default=3.0,
        help="Horizontal speed in m/s (default: 3.0, slow movement)",
    )
    parser.add_argument(
        "--heading",
        type=float,
        default=45.0,
        help="Heading in degrees (0=N, 90=E, default: 45)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=300.0,
        help="Duration in seconds (default: 300)",
    )
    parser.add_argument(
        "--sample-hz",
        type=float,
        default=10.0,
        help="Sample rate in Hz (default: 10, matches gps-sdr-sim motion files)",
    )
    parser.add_argument(
        "--climb-rate",
        type=float,
        default=0.0,
        help="Vertical rate in m/s (default: 0)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="straight_path.csv",
        help="Output CSV path",
    )

    args = parser.parse_args()

    if args.sample_hz <= 0:
        raise ValueError("--sample-hz must be > 0")
    if args.duration < 0:
        raise ValueError("--duration must be >= 0")
    if not (-90.0 <= args.lat <= 90.0):
        raise ValueError("--lat must be in [-90, 90]")
    if not (-180.0 <= args.lon <= 180.0):
        raise ValueError("--lon must be in [-180, 180]")

    rows = generate_path(
        start_lat=args.lat,
        start_lon=args.lon,
        start_alt=args.alt,
        speed_mps=args.speed,
        heading_deg=args.heading,
        duration_s=args.duration,
        sample_hz=args.sample_hz,
        climb_mps=args.climb_rate,
    )

    with open(args.output, "w") as output_file:
        for t, x, y, z in rows:
            output_file.write(f"{t:5.1f},{x:12.3f}, {y:12.3f}, {z:12.3f}\n")

    print(f"Wrote {len(rows)} points to {args.output}")
    print("Use with: gps-sdr-sim -e <brdc_file> -u <output_csv>")


if __name__ == "__main__":
    main()
