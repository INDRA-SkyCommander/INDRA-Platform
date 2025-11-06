# /src/gui - INDRA GUi

## INDRA GUI Main Module
**File:** GUI.py

**Description:**
This file defines the main graphical user interface for the INDRA software suite. The GUI provides functionality to:
 - Start, stop, and monitor live network scans
 - Display detected hosts and target information
 - Control modules and options
 - Run exploits through exploitation framework
 - Display live visual data through the ImagePlayer widget

## Package initializer
**File:** __init__.py

**Description:**
Package init for the GUI package. Provides a simple re-export so callers can do : 'from indra_gui inport MainGUI'. Keeps the GUI package importable as a module.
