# INDRA GUI

## Overview

The **INDRA GUI** is the main graphical interface for the INDRA software
suite. It provides a centralized dashboard for wireless scanning, target
selection, exploit execution, live video visualization, and system
logging.

Location:

    /src/gui

------------------------------------------------------------------------

## Main Files

### `GUI.py`

Defines the primary application window and all GUI logic.

Key responsibilities: - Start, stop, and auto-run wireless scans -
Display and filter discovered targets - Select network interfaces and
exploit modules - Execute exploits in background threads - Display live
H.264 video decoded from sniffed data - Show real-time system logs

Core class:

``` python
class IndraGUI(tb.Window):
```

------------------------------------------------------------------------

### `__init__.py`

Package initializer that re-exports the main GUI class:

``` python
from indra_gui import IndraGUI
```

------------------------------------------------------------------------

## Features

-   **Scanning** -- Manual or automatic scans with interface selection
-   **Host List** -- Filterable list of detected targets
-   **Exploitation** -- Run exploit modules against selected targets
-   **Live Video Feed** -- Real-time H.264 decoding via PyAV
-   **System Log** -- Asynchronous terminal-style logging
-   **Utility Options** -- Restart network adapter, stop monitor mode

------------------------------------------------------------------------

## Backend Integration

The GUI integrates with backend utilities and modules: - `utils.scan`
for wireless scanning - `utils.module_setup` for exploit discovery -
`utils.sudo_exec` for privileged system commands

Shared data files are managed under:

    /data

------------------------------------------------------------------------

## Notes

-   Requires root privileges for scanning and exploits
-   Only one scan or exploit runs at a time
-   Designed as the primary user-facing interface for INDRA


