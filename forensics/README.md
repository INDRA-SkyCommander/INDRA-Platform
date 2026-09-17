# INDRA Digital Forensics

Post-capture forensic analysis of a **grounded / captured** drone. This is the
passive counterpart to the active `modules/` (deauth, reauth, control, ...):
those attack a drone; these run *after* one is in hand and read data off it.

> **Authorized use only.** Run these tools only against drones and storage you
> own or have explicit permission to examine. Handle extracted data responsibly
> and preserve its integrity (hashing) for chain-of-custody.

## Scope of this folder

| Sub-package    | Purpose                                                        | Status |
|----------------|---------------------------------------------------------------|--------|
| `acquisition/` | Get data **off** the drone onto local disk (wired USB)        | ✅ USB |

Downstream modules (flight-log parsing, media metadata, steganography, SHA-256
verification, reporting) consume the output produced here. They are separate
tasks; this folder currently delivers the **Acquisition** step only.

## `acquisition/usb_extractor.py` — Wired (USB) extraction

Detects a connected DJI drone / USB storage, copies everything off it, hashes
each file, and writes a manifest — sorted into the buckets the Forensics tab
cares about.

### What it does
1. **Detect** a DJI device (USB vendor id `2ca3`) and enumerate mounted USB /
   removable volumes (`lsusb` + `lsblk -J`).
2. **List** the available data sources (each mounted volume = one source).
3. **Copy** every accessible file to local disk, preserving original filenames
   and directory structure.
4. **Categorize** for downstream use:
   - `flight_logs/` — `.DAT`, `.TXT`
   - `media/` — images & video (`.jpg .png .dng .mp4 .mov .lrv ...`)
   - `other/` — everything else
5. **Hash** every copied file with **SHA-256** and record a JSON manifest.
6. **Fail gracefully** — drone not detected, volume not mounted, permission
   errors, or an interrupted copy are logged and recorded, never crash.

### Output layout
```
<output_root>/<session_id>/
    flight_logs/<source>/<original/sub/dirs>/...
    media/<source>/<original/sub/dirs>/...
    other/<source>/<original/sub/dirs>/...
    manifest.json
```
`<output_root>` defaults to `data/extracted/` (the `data/` dir is git-ignored,
so extracted evidence is never committed).

### manifest.json
```jsonc
{
  "tool": "INDRA usb_extractor",
  "session_id": "20260910_143512_ab12cd",
  "extraction_started": "...", "extraction_completed": "...",
  "interrupted": false,
  "dji_device_detected": true,
  "sources": [ { "mountpoint": "...", "label": "...", "fstype": "...", ... } ],
  "files": [
    {
      "original_path": "...", "copied_path": "...", "relative_path": "...",
      "source_label": "...", "category": "flight_logs",
      "file_type": ".dat", "size_bytes": 12345,
      "sha256": "....", "extracted_at": "..."
    }
  ],
  "errors": [ { "path": "...", "error": "..." } ],
  "summary": { "total_files": 5, "total_bytes": 73,
               "counts": { "flight_logs": 2, "media": 2, "other": 1 },
               "error_count": 0 }
}
```

### Usage
```bash
# Auto-detect a connected drone / USB storage and extract:
python3 forensics/acquisition/usb_extractor.py

# Extract from an explicit already-mounted path — no real drone needed,
# ideal for offline testing with a sample SD card or a folder of test files:
python3 forensics/acquisition/usb_extractor.py --source /media/user/DJI_SD

# Custom output location / session id:
python3 forensics/acquisition/usb_extractor.py --output-dir /tmp/out --session-id case001
```
Exit codes: `0` extracted ≥1 file · `2` nothing found to extract · `1` fatal error.

```python
# Or import it (e.g. from the Forensics tab later):
from forensics.acquisition import USBExtractor
manifest = USBExtractor().extract()          # returns the manifest dict
```

### Notes & limits
- **Python 3 standard library only** — no third-party or Go dependencies.
  (DroneXtract is written in Go and was used **only** as a design reference for
  the data model and file-type handling; no Go tooling is introduced.)
- Runs on Linux (the INDRA Ubuntu VM). Detection uses `lsusb` / `lsblk`; if the
  drone/SD is mounted somewhere already, `--source <path>` bypasses detection
  entirely.
- **Internal vs. SD card:** the extractor records each mounted volume's
  label / model / size, but does not attempt to reliably declare which is
  "internal" vs "SD" — that is drone/firmware-specific and left for the operator
  to judge from the recorded metadata.
- Wireless extraction is a **separate future module**, intentionally out of scope
  here.
```
