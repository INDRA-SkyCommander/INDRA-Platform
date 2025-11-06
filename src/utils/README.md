# /src/utils — INDRA Utilities

## iwlist parser
**File:** iwlist_parse.py  
**Description:**  
Parsing utilities for `iwlist` output. The parser extracts and normalizes:  
- Cells / SSID (ESSID) names  
- Quality (converted to percent), channel, signal level  
- MAC addresses and encryption info  
- Helper functions: `parse_cell()`, `get_cells()` and formatting rules/columns

## Module discovery
**File:** module_setup.py  
**Description:**  
Scans the `modules/` directory and returns a list of visible module folder names for GUI dropdowns. Provides `module_setup()`.

## Scanner orchestrator
**File:** scan.py  
**Description:**  
Performs `iwlist <interface> scan`, persists raw output, parses it, and writes a compact `scan_results.txt`. Provides `scan(interface)` that returns a mapping of target name to a detail list.

## Privileged command wrapper
**File:** sudo_exec.py  
**Description:**  
Small wrapper to run privileged shell commands and capture output. Provides `sudo_exec(cmd)`.

## Package initializer
**File:** __init__.py  
**Description:**  
Re-exports core helpers so callers can `from utils import scan, module_setup, sudo_exec`.

## UI color constants
**File:** colors.py  
**Description:**  
Centralized UI color constants used by the GUI (hex values and Tkinter variation names).
