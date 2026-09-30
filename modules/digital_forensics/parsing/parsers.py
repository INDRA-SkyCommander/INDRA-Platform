import csv
import os
import xml.etree.ElementTree as ET
from helpers import (
    check_file_format, print_error, print_error_log,
    gen_row_string, gen_table_header, gen_table_header_modified, gen_table_footer,
    BLUE, RESET,
)

try:
    import gpxpy
    GPXPY_AVAILABLE = True
except ImportError:
    GPXPY_AVAILABLE = False


# ── CSV ───────────────────────────────────────────────────────────────────────

class DJI_CSV_Parser:
    def __init__(self, file_name: str):
        if not check_file_format(file_name, ".csv"):
            print_error("INVALID FILE FORMAT. MUST BE CSV FILE")
            self._file_name = None
            return
        self._file_name = file_name

    def parse_contents(self):
        if self._file_name is None:
            return
        try:
            with open(self._file_name, newline='', encoding='utf-8') as f:
                records = list(csv.reader(f))
        except Exception as e:
            print_error_log("INVALID FILE. UNABLE TO OPEN", e)
            return

        columns = records[0]
        for count, record in enumerate(records):
            gen_table_header("Row " + str(count), count == 0)
            for i, value in enumerate(record):
                gen_row_string(columns[i], value)
            gen_table_footer()


# ── KML ───────────────────────────────────────────────────────────────────────

class DJI_KML_Parser:
    def __init__(self, file_name: str):
        if not check_file_format(file_name, ".kml"):
            print_error("INVALID FILE FORMAT. MUST BE KML FILE")
            self._file_name = None
            return
        self._file_name = file_name

    def parse_contents(self):
        if self._file_name is None:
            return
        try:
            with open(self._file_name, 'rb') as f:
                content = f.read()
        except Exception as e:
            print_error_log("INVALID FILE. ERROR READING CONTENTS", e)
            return
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            print_error_log("INVALID FILE. ERROR READING CONTENTS", e)
            return

        ns = root.tag.split("}")[0] + "}" if "}" in root.tag else ""
        for placemark in root.findall(f".//{ns}Placemark"):
            point = placemark.find(f"{ns}Point")
            if point is not None:
                coords_elem = point.find(f"{ns}coordinates")
                if coords_elem is not None and coords_elem.text:
                    v = coords_elem.text.strip().split(",")
                    gen_table_header("Home Point Information", True)
                    gen_row_string("Coordinates", "(" + v[0] + "," + v[1] + ")")
                    gen_row_string("Altitude", v[2] + " ft")
                    gen_table_footer()

            line_string = placemark.find(f"{ns}LineString")
            if line_string is not None:
                coords_elem = line_string.find(f"{ns}coordinates")
                if coords_elem is not None and coords_elem.text:
                    for c_index, coor in enumerate(coords_elem.text.split("\n")):
                        v = coor.split(",")
                        if len(coor) > 0 and len(v) > 1:
                            gen_table_header("Coordinate Point " + str(c_index + 1), False)
                            gen_row_string("Coordinates", "(" + v[0] + ", " + v[1] + ")")
                            gen_row_string("Altitude", v[2] + " ft")
                            gen_table_footer()


# ── GPX ───────────────────────────────────────────────────────────────────────

def _format_duration(seconds) -> str:
    if not seconds:
        return "0s"
    h, m, s = int(seconds // 3600), int((seconds % 3600) // 60), int(seconds % 60)
    parts = ([f"{h}h"] if h else []) + ([f"{m}m"] if m else []) + [f"{s}s"]
    return " ".join(parts)


def _get_gpx_info(gpx_data) -> str:
    lines = []
    l2 = gpx_data.length_2d() or 0.0
    l3 = gpx_data.length_3d() or 0.0
    lines += [f" - Length 2D: {l2 / 1000:.3f} km", f" - Length 3D: {l3 / 1000:.3f} km"]

    md = gpx_data.get_moving_data()
    if md:
        lines += [
            f" - Moving time: {_format_duration(md.moving_time)}",
            f" - Stopped time: {_format_duration(md.stopped_time)}",
            f" - Max speed: {(md.max_speed or 0.0):.2f} m/s",
        ]

    ud = gpx_data.get_uphill_downhill()
    if ud:
        lines += [
            f" - Total uphill: {(ud.uphill or 0.0):.2f} m",
            f" - Total downhill: {(ud.downhill or 0.0):.2f} m",
        ]

    tb = gpx_data.get_time_bounds()
    if tb and tb.start_time:
        lines += [f" - Started: {tb.start_time}", f" - Ended: {tb.end_time}"]

    n = gpx_data.get_points_no()
    lines.append(f" - Points: {n}")
    if n > 1 and l2 > 0:
        lines.append(f" - Avg distance between points: {l2 / (n - 1):.2f} m")

    return "\n".join(lines)


class DJI_GPX_Parser:
    def __init__(self, file_name: str):
        if not check_file_format(file_name, ".gpx"):
            print_error("INVALID FILE FORMAT. MUST BE GPX FILE")
            self._file_name = None
            return
        self._file_name = file_name

    def parse_contents(self):
        if self._file_name is None:
            return
        if not GPXPY_AVAILABLE:
            print_error("gpxpy library not installed. Run: pip install gpxpy")
            return
        try:
            with open(self._file_name, 'r', encoding='utf-8') as f:
                gpx_data = gpxpy.parse(f)
        except Exception as e:
            print_error_log("INVALID FILE. ERROR READING CONTENTS", e)
            return

        print(BLUE + "File: " + os.path.abspath(self._file_name) + "\n" + RESET)
        print(BLUE + _get_gpx_info(gpx_data) + RESET)
