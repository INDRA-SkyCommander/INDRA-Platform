"""
telemetry_python/telemetry.py

Python port of the DroneXtract `telemetry` package.
Provides two tools:

  1. DJIFlightPathMap — reads a CSV with latitude/longitude columns and
     renders a static PNG map of the flight path.
  2. DJITelemetryVisualizations — reads a DJI flight-record CSV and
     renders an ASCII time-series chart for any of 45 telemetry channels.

Entry point: execute_telemetry(index)
  index=1  →  Flight Path Map
  index=2  →  Telemetry Visualizations
"""

import csv
import os
import sys
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

# ── Colour setup ──────────────────────────────────────────────────────────────

try:
    from colorama import Fore, Style, init as _colorama_init
    _colorama_init(autoreset=True)
    BLUE  = Fore.BLUE
    RED   = Fore.RED
    CYAN  = Fore.CYAN
    GREEN = Fore.GREEN
    RESET = Style.RESET_ALL
except ImportError:
    BLUE = RED = CYAN = GREEN = RESET = ""

# ── .env loading ──────────────────────────────────────────────────────────────

try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(_env_path)
except ImportError:
    pass


def _get_env_int(key: str, default: int) -> int:
    val = os.getenv(key, "")
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


FLIGHT_MAP_DOWNSAMPLE    = _get_env_int("FLIGHT_MAP_DOWNSAMPLE", 100)
TELEMETRY_VIS_DOWNSAMPLE = _get_env_int("TELEMETRY_VIS_DOWNSAMPLE", 200)

# ── Helper utilities (ported from helpers package) ────────────────────────────

def file_input_string() -> str:
    return input("\n ENTER FILE PATH > ").strip()


def output_path_string() -> str:
    return input("\n ENTER OUTPUT PATH > ").strip()


def option(min_val: int, max_val: int) -> int:
    selection = input("\n ENTER INPUT > ").strip()
    try:
        num = int(selection)
    except ValueError:
        print(RED + "  [!] INVALID INPUT" + RESET)
        return option(min_val, max_val)

    if num == min_val:
        print(BLUE + " Farewell and fly high!" + RESET)
        sys.exit(0)
    elif num == max_val + 1:
        return -1
    elif min_val < num <= max_val:
        return num
    else:
        print(RED + "  [!] INVALID INPUT" + RESET)
        return option(min_val, max_val)


def check_file_format(path: str, exten: str) -> bool:
    return Path(path).suffix.lower() == exten


def gen_table_header(name: str):
    print(BLUE + "\n    ╔══════════════════════════════════════════════════════════════════════════════╗" + RESET)
    amount = (78 - len(name)) // 2
    print(BLUE + "    ║" + " " * amount + name + " " * (amount + 1) + "║" + RESET)
    print(BLUE + "    ╠══════════════════════════════════════════════════════════════════════════════╣" + RESET)


def gen_row_string(intro: str, input_val: str):
    total_count = 4 + len(intro) + len(input_val) + 2
    use_count = max(0, 80 - total_count)
    val = "    ║ " + intro + ": " + input_val + " " * use_count + " ║"
    print(BLUE + val + RESET)


def gen_table_footer():
    print(BLUE + "    ╚══════════════════════════════════════════════════════════════════════════════╝" + RESET)


def print_log(message: str):
    print(CYAN + message + RESET)


def print_error(message: str):
    print(RED + "[ERROR] " + message + RESET)


def print_error_log(message: str, err: Exception):
    print(RED + message + RESET)
    logging.error("[ERROR] %s", str(err))


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class Coordinate:
    latitude: float
    longitude: float


# ── Downsampling ──────────────────────────────────────────────────────────────

def _downsample_coordinates(coordinates: List[Coordinate], target: int) -> List[Coordinate]:
    length = len(coordinates)
    if target >= length:
        return coordinates
    ratio = length / target
    result = []
    for i in range(target):
        start = int(i * ratio)
        end   = int((i + 1) * ratio)
        avg_lat = sum(c.latitude  for c in coordinates[start:end]) / (end - start)
        avg_lon = sum(c.longitude for c in coordinates[start:end]) / (end - start)
        result.append(Coordinate(avg_lat, avg_lon))
    return result


def _downsample_array(data: List[float], target: int) -> List[float]:
    length = len(data)
    if target >= length:
        return data
    ratio = length / target
    result = []
    for i in range(target):
        start = int(i * ratio)
        end   = int((i + 1) * ratio)
        result.append(sum(data[start:end]) / (end - start))
    result[0] = data[0]
    return result


# ── Flight Path Map ───────────────────────────────────────────────────────────

class DJIFlightPathMap:
    """Reads a DJI CSV flight record and renders a static PNG flight-path map."""

    def __init__(self, file_name: str, output_path: str):
        self._file_name   = file_name
        self._output_path = output_path

    def execute_flight_path_analysis(self):
        self._print_gps_coordinates()

    def _print_gps_coordinates(self):
        try:
            with open(self._file_name, newline='', encoding='utf-8') as f:
                records = list(csv.reader(f))
        except Exception as e:
            print_error_log("INVALID FILE. UNABLE TO OPEN", e)
            return

        if not records:
            print_error("CSV FILE IS EMPTY")
            return

        columns = records[0]
        coords: List[Coordinate] = []

        for record in records[1:]:
            lat_val = 0.0
            lon_val = 0.0
            for i, value in enumerate(record):
                if i >= len(columns):
                    continue
                try:
                    val = float(value)
                except ValueError:
                    continue
                if columns[i] == "latitude" and val != 0:
                    lat_val = val
                if columns[i] == "longitude" and val != 0:
                    lon_val = val
            if lat_val != 0.0 and lon_val != 0.0:
                coords.append(Coordinate(lat_val, lon_val))

        generate_map_output(coords, self._output_path)


def generate_map_output(coords: List[Coordinate], output_path: str):
    """Render flight path coordinates to a PNG static map."""
    if not output_path:
        output_path = "flight-path-map.png"

    if len(coords) > FLIGHT_MAP_DOWNSAMPLE:
        coords = _downsample_coordinates(coords, FLIGHT_MAP_DOWNSAMPLE)

    if not check_file_format(output_path, ".png"):
        print_error("INVALID OUTPUT FILE FORMAT. MUST BE PNG FILE")
        return

    try:
        from staticmap import StaticMap, CircleMarker, Line
    except ImportError:
        print_error("staticmap library not installed. Run: pip install staticmap")
        return

    m = StaticMap(400, 300)

    for coord in coords:
        # staticmap expects (longitude, latitude) order
        m.add_marker(CircleMarker((coord.longitude, coord.latitude), 'red', 16))

    for i in range(len(coords) - 1):
        p1 = (coords[i].longitude,     coords[i].latitude)
        p2 = (coords[i + 1].longitude, coords[i + 1].latitude)
        m.add_line(Line([p1, p2], 'red', 6))

    _print_coordinates(coords, len(coords) <= 10)

    try:
        image = m.render()
        image.save(output_path)
    except Exception as e:
        print_error_log("FAILED TO RENDER MAP", e)
        return

    print_log("Created Flight Path Map at " + output_path)


def _print_coordinates(coordinates: List[Coordinate], downsampled: bool):
    label = "Downsampled GPS Coordinates" if downsampled else "GPS Coordinates"
    gen_table_header(label)
    for i, coord in enumerate(coordinates):
        gen_row_string(f"Coordinate {i + 1}", f"({coord.latitude}, {coord.longitude})")
    gen_table_footer()


# ── Telemetry Visualizations ──────────────────────────────────────────────────

_INDICATORS = [
    "height_above_takeoff(feet)", "height_above_ground_at_drone_location(feet)",
    "ground_elevation_at_drone_location(feet)", "ground_elevation_at_drone_location(feet)",
    "altitude_above_seaLevel(feet)", "height_sonar(feet)", "speed(mph)", "distance(feet)",
    "mileage(feet)", "satellites", "gpslevel", "voltage(v)", "max_altitude(feet)",
    "max_ascent(feet)", "max_speed(mph)", "max_distance(feet)", "xSpeed(mph)", "ySpeed(mph)",
    "zSpeed(mph)", "compass_heading(degrees)", "pitch(degrees)", "roll(degrees)",
    "rc_elevator", "rc_aileron", "rc_throttle", "rc_rudder", "rc_elevator(percent)",
    "rc_aileron(percent)", "rc_throttle(percent)", "rc_rudder(percent)",
    "gimbal_heading(degrees)", "gimbal_pitch(degrees)", "gimbal_roll(degrees)",
    "battery_percent", "voltageCell1", "voltageCell2", "voltageCell3", "voltageCell4",
    "voltageCell5", "voltageCell6", "current(A)", "battery_temperature(f)",
    "altitude(feet)", "ascent(feet)", "flycStateRaw",
]

_PRINT_INDICATORS = [
    "Height Above Takeoff (feet)", "Height Above Ground at Drone Location (feet)",
    "Ground Elevation at Drone Location (feet)", "Ground Elevation at Drone Location (feet)",
    "Altitude Above Sea Level (feet)", "Height Sonar (feet)", "Speed (mph)",
    "Distance (feet)", "Mileage (feet)", "Satellites", "GPS Level", "Voltage (V)",
    "Max Altitude (feet)", "Max Ascent (feet)", "Max Speed (mph)", "Max Distance (feet)",
    "X Speed (mph)", "Y Speed (mph)", "Z Speed (mph)", "Compass Heading (degrees)",
    "Pitch (degrees)", "Roll (degrees)", "RC Elevator", "RC Aileron", "RC Throttle",
    "RC Rudder", "RC Elevator (percent)", "RC Aileron (percent)", "RC Throttle (percent)",
    "RC Rudder (percent)", "Gimbal Heading (degrees)", "Gimbal Pitch (degrees)",
    "Gimbal Roll (degrees)", "Battery Percent", "Voltage Cell 1", "Voltage Cell 2",
    "Voltage Cell 3", "Voltage Cell 4", "Voltage Cell 5", "Voltage Cell 6",
    "Current (A)", "Battery Temperature (F)", "Altitude (feet)", "Ascent (feet)",
    "Flyc State Raw",
]


class DJITelemetryVisualizations:
    """Reads a DJI flight-record CSV and plots an ASCII chart for a chosen telemetry channel."""

    def __init__(self, file_name: str):
        if not check_file_format(file_name, ".csv"):
            print_error("INVALID FILE FORMAT. MUST BE CSV FILE")
            self._file_name = None
            return
        self._file_name = file_name

    def execute_telemetry_visualizations(self):
        if self._file_name is None:
            return
        value = _generate_options()
        if value == -1:
            return
        self._generate_graph(value)

    def _generate_graph(self, index: int):
        col_index = index - 1  # convert 1-based user selection to 0-based column index
        try:
            with open(self._file_name, newline='', encoding='utf-8') as f:
                records = list(csv.reader(f))
        except Exception as e:
            print_error_log("INVALID FILE. UNABLE TO OPEN", e)
            return

        output: List[float] = []
        for record in records[1:]:  # skip header row
            if col_index < len(record):
                try:
                    output.append(float(record[col_index]))
                except ValueError:
                    output.append(0.0)

        if len(output) > TELEMETRY_VIS_DOWNSAMPLE:
            output = _downsample_array(output, TELEMETRY_VIS_DOWNSAMPLE)

        try:
            import plotext as plt
        except ImportError:
            print_error("plotext library not installed. Run: pip install plotext")
            return

        plt.clear_figure()
        plt.plot(output)
        plt.title(_PRINT_INDICATORS[col_index])
        plt.plot_size(100, 12)
        print(CYAN, end="")
        plt.show()
        print(RESET, end="")


def _generate_options() -> int:
    gen_table_header("Select Value to Visualize")
    for i, label in enumerate(_PRINT_INDICATORS):
        gen_row_string(str(i + 1), label)
    gen_row_string(str(len(_PRINT_INDICATORS) + 1), "Back to Main Menu")
    gen_row_string("0", "Exit DroneXtract")
    gen_table_footer()
    return option(0, len(_PRINT_INDICATORS))


# ── Top-level dispatcher ──────────────────────────────────────────────────────

def execute_telemetry(index: int):
    """
    Dispatcher mirroring ExecuteTelemetry in the Go package.

    Parameters
    ----------
    index : int
        1  →  Flight Path Map
        2  →  Telemetry Visualizations
    """
    file_path = file_input_string()
    if index == 1:
        output = output_path_string()
        DJIFlightPathMap(file_path, output).execute_flight_path_analysis()
    elif index == 2:
        DJITelemetryVisualizations(file_path).execute_telemetry_visualizations()


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(BLUE + "\n DroneXtract Telemetry" + RESET)
    gen_table_header("Select Mode")
    gen_row_string("1", "Flight Path Map")
    gen_row_string("2", "Telemetry Visualizations")
    gen_row_string("0", "Exit")
    gen_table_footer()
    try:
        choice = input("\n ENTER INPUT > ").strip()
        num = int(choice)
        if num == 0:
            sys.exit(0)
        execute_telemetry(num)
    except (ValueError, KeyboardInterrupt):
        sys.exit(0)
