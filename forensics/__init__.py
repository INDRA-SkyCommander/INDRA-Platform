"""
INDRA Digital Forensics package.

Post-capture forensic analysis of a grounded/captured drone. Separate from the
active-attack `modules/` package (deauth, reauth, control, ...): these components
run *after* a drone is in hand and read data off it rather than attacking it.

Sub-packages:
    acquisition  - getting data off the drone (wired USB now; wireless later)
"""
