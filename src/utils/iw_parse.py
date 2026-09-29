"""
Parses the output of `iw dev <interface> scan` into per-cell records.

Used alongside iwlist_parse.py: `iw` talks to the kernel over nl80211
directly, which is what the scan adapters actually support, so it's the
preferred scan method. iwlist relies on the legacy Wireless Extensions
(WEXT) ioctl API, which those drivers implement poorly, so it's kept only
as a fallback (see scan.py) and needs iwlist_parse.py, not this module.
"""

import re

_BSS_RE = re.compile(r"^BSS\s+([0-9a-fA-F:]{17})")
_FREQ_RE = re.compile(r"^freq:\s*(\d+)")
_SIGNAL_RE = re.compile(r"^signal:\s*(-?\d+(?:\.\d+)?)\s*dBm")


def get_cells(fstring):
    """
    Splits `iw scan` output into a list of cells, one per BSS block.

    Each cell is itself a list of the raw output lines belonging to that
    access point, mirroring the shape the rest of the app expects.

    Args:
        fstring (str): The output of `iw dev <interface> scan`.

    Returns:
        List[List[str]]: One entry per access point found.
    """
    cell_list = []

    for line in fstring.split("\n"):
        if _BSS_RE.match(line.strip()):
            cell_list.append([])
        if cell_list:
            cell_list[-1].append(line)

    return cell_list


def get_address(cell):
    """Extracts the BSSID (MAC address) from a cell's `BSS` line."""
    for line in cell:
        m = _BSS_RE.match(line.strip())
        if m:
            return m.group(1)
    return "N/A"


def get_name(cell):
    """Extracts the SSID from a cell. Returns '' for a hidden/blank SSID."""
    for line in cell:
        stripped = line.strip()
        if stripped.startswith("SSID:"):
            return stripped[len("SSID:"):].strip()
    return ""


def get_channel(cell):
    """Extracts the channel number, derived from the `freq:` line (MHz)."""
    for line in cell:
        m = _FREQ_RE.match(line.strip())
        if m:
            return str(_freq_to_channel(int(m.group(1))))
    return "N/A"


def get_signal_level(cell):
    """Extracts the signal level in dBm from the `signal:` line."""
    for line in cell:
        m = _SIGNAL_RE.match(line.strip())
        if m:
            return f"{m.group(1)} dBm"
    return "N/A"


def get_quality(cell):
    """
    Approximates a 0-100% quality figure from the dBm signal level, using
    the same linear scale (-100 dBm = 0%, -50 dBm and above = 100%) that
    iwconfig/NetworkManager conventionally use.
    """
    for line in cell:
        m = _SIGNAL_RE.match(line.strip())
        if m:
            dbm = float(m.group(1))
            percent = max(0, min(100, round(2 * (dbm + 100))))
            return str(int(percent)).rjust(3) + " %"
    return "N/A"


def get_encryption(cell):
    """Determines encryption type from the capability/RSN/WPA lines."""
    has_privacy = False
    has_rsn = False
    has_wpa = False

    for line in cell:
        stripped = line.strip()
        if stripped.startswith("capability:") and "Privacy" in stripped:
            has_privacy = True
        elif stripped.startswith("RSN:"):
            has_rsn = True
        elif stripped.startswith("WPA:"):
            has_wpa = True

    if not has_privacy:
        return "Open"
    if has_rsn:
        return "WPA v.2"
    if has_wpa:
        return "WPA v.1"
    return "WEP"


def _freq_to_channel(freq):
    """Converts a frequency in MHz to a Wi-Fi channel number (2.4/5/6 GHz)."""
    if freq == 2484:
        return 14
    if 2412 <= freq <= 2472:
        return (freq - 2407) // 5
    if 5955 <= freq <= 7115:
        return (freq - 5950) // 5
    if 5180 <= freq <= 5885:
        return (freq - 5000) // 5
    return freq
