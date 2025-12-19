# INDRA utils

Small helper functions used by the INDRA project (Wi‑Fi scanning + module discovery).

## Requirements
- Python 3
- Linux with `iwlist` available (commonly from the `wireless-tools` package)
- A wireless interface name (default: `wlan0`)

## Quick start

```python
from src.utils import scan, module_setup, sudo_exec

# 1) Scan for nearby Wi‑Fi networks
results = scan(interface="wlan0")

# 2) List available INDRA modules (folders under <project_root>/modules)
modules = module_setup()

# 3) Run a privileged command
sudo_exec(["whoami"])
```

## What each file does

### `scan.py`
- Runs `iwlist <interface> scan`
- Writes files under `src/data/`:
  - `raw_output.txt` (raw `iwlist` output)
  - `scan_results.txt` (one target per line)

Return value:
- Usually returns a dict keyed by `"SSID - MAC"` (SSID may be `"N/A"`).
- Each dict value is a list: `[name, address, quality, channel, signal_level, encryption]`.

Errors / edge cases:
- Returns `"SCAN_ERROR_UNSUPPORTED_INTERFACE"` if the interface can’t scan (or doesn’t exist)
- Returns `"SCAN_ERROR_GENERIC"` for other scan failures
- May return `None` if the scan output is empty (blank results)

### `iwlist_parse.py`
Parsing helpers used by `scan()`, including:
`get_cells`, `get_name`, `get_address`, `get_quality`, `get_channel`, `get_signal_level`, `get_encryption`.

### `module_setup.py`
`module_setup()` returns a list of visible module directory names found in `<project_root>/modules`.

### `sudo_exec.py`
`sudo_exec(cmd)` runs the command with `sudo` via `subprocess.run(..., shell=True)` and returns the `CompletedProcess`.
(Stdout/stderr are not captured unless the implementation is changed.)

## Notes
- If your Wi‑Fi interface isn’t `wlan0`, replace it with your system’s name (check `ip link`).
