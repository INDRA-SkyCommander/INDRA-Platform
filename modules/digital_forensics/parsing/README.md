# parsing

Python port of the DroneXtract `parsing` package (originally written in Go). Parses DJI drone flight data files in CSV, KML, and GPX formats and prints their contents as formatted tables to the terminal.

---

> **Must install dependencies before use:**
> ```bash
> pip install colorama gpxpy
> ```

---

## Files

| File | Description |
|------|-------------|
| `helpers.py` | Shared utilities: color output, table formatting, file validation, and the `execute_parser` dispatcher |
| `parsers.py` | The three parser classes: `DJI_CSV_Parser`, `DJI_KML_Parser`, `DJI_GPX_Parser` |

---

## Dependencies

```bash
pip install colorama gpxpy
```

| Package | Purpose |
|---------|---------|
| `colorama` | Terminal color output (replaces Go's `go-color`) |
| `gpxpy` | GPX file parsing (replaces Go's `gpxgo`) |

---

## Usage

### Dispatcher

Call `execute_parser` with an index to prompt for a file path and run the matching parser:

```python
from helpers import execute_parser

execute_parser(1)  # CSV
execute_parser(2)  # KML
execute_parser(3)  # GPX
```

### Individual parsers

```python
from parsers import DJI_CSV_Parser, DJI_KML_Parser, DJI_GPX_Parser

DJI_CSV_Parser("flight.csv").parse_contents()
DJI_KML_Parser("flight.kml").parse_contents()
DJI_GPX_Parser("flight.gpx").parse_contents()
```

If the file extension does not match the expected format, an error is printed and parsing is skipped.

---

## Supported File Formats

### CSV (`.csv`)
Reads any DJI Airdata-style CSV. Each row is printed as a table with column names as labels and cell values as data.

### KML (`.kml`)
Parses DJI KML flight path files. Extracts:
- **Home Point** — coordinates and altitude from `<Point>` placemarks
- **Flight Path** — each coordinate from `<LineString>` placemarks, numbered sequentially

Handles KML files with or without an XML namespace prefix.

### GPX (`.gpx`)
Parses GPX files exported from DJI Airdata. Prints the absolute file path followed by a flight summary:
- 2D and 3D track length
- Moving and stopped time
- Max speed
- Total uphill / downhill elevation change
- Start and end timestamps
- Total point count and average distance between points

---

## Output Format

All output is printed to the terminal in blue using box-drawing characters:

```
    ╔══════════════════════════════════════════════════════════════════════════════╗
    ║                            Home Point Information                            ║
    ╠══════════════════════════════════════════════════════════════════════════════╣
    ║ Coordinates: (-118.371159,33.882275)                                         ║
    ║ Altitude: 24.85 ft                                                           ║
    ╚══════════════════════════════════════════════════════════════════════════════╝
```

---

## Virtual Environment (recommended)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
