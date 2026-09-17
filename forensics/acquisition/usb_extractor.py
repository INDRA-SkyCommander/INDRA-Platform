#!/usr/bin/env python3
"""
INDRA Forensics - Wired (USB) Data Extraction Module
=====================================================

Handles the "Acquisition" step of the INDRA digital-forensics workflow for a
*wired* connection to a captured DJI drone (Phantom family in scope). It:

    1. Detects a DJI device / USB mass-storage volumes plugged into the host
    2. Lists the available data sources (mounted USB / removable volumes)
    3. Copies every accessible file to local disk, preserving names + structure
    4. Sorts files into the categories the Forensics tab cares about
       (flight_logs / media / other)
    5. Hashes every copied file with SHA-256 and writes a JSON manifest
    6. Fails gracefully - clear messages, never a bare crash

Output layout (per extraction session):

    <output_root>/<session_id>/flight_logs/<source>/<original/sub/dirs>/file
    <output_root>/<session_id>/media/<source>/<original/sub/dirs>/file
    <output_root>/<session_id>/other/<source>/<original/sub/dirs>/file
    <output_root>/<session_id>/manifest.json

`<output_root>` defaults to `<project>/data/extracted` (the INDRA `data/` dir is
already git-ignored, so extracted evidence is never accidentally committed).

Design references (concepts only, NOT dependencies): DroneXtract (Go) and DROP.
DroneXtract is Go - this module borrows its *data model* and *file-type handling*
and re-implements them in idiomatic Python. No Go tooling is introduced.

Stack: Python 3 standard library only (os, shutil, hashlib, json, subprocess...).
No third-party packages required.

Usage (standalone):
    # Auto-detect a connected drone / USB storage and extract:
    python3 forensics/acquisition/usb_extractor.py

    # Extract from an explicit already-mounted path (great for offline testing
    # with a sample SD card or a folder of test files - no drone needed):
    python3 forensics/acquisition/usb_extractor.py --source /media/user/DJI_SD

    # Custom output location / session id:
    python3 forensics/acquisition/usb_extractor.py --output-dir /tmp/out --session-id case001

Usage (import, e.g. from the Forensics tab later):
    from forensics.acquisition import USBExtractor
    manifest = USBExtractor().extract()          # returns the manifest dict
"""

import os
import sys
import json
import uuid
import shutil
import hashlib
import argparse
import subprocess
from datetime import datetime, timezone


# ======================================================================
# Logging helpers (match INDRA module print conventions: [*], [+], ...)
# ======================================================================

def log_info(msg):
    print(f"[*] {msg}", flush=True)


def log_ok(msg):
    print(f"[+] {msg}", flush=True)


def log_warn(msg):
    print(f"[!] WARNING: {msg}", flush=True)


def log_err(msg):
    print(f"[x] ERROR: {msg}", file=sys.stderr, flush=True)


# ======================================================================
# Constants: DJI identity + downstream file-type buckets
# ======================================================================

# DJI Technology Co., Ltd USB vendor id (seen in `lsusb`).
DJI_USB_VENDOR_ID = "2ca3"

# Flight logs the parsing module will consume. .DAT = binary (often encrypted,
# richer); .TXT = human-readable flight record.
FLIGHT_LOG_EXTS = {".dat", ".txt"}

# Media for the metadata + steganography modules. Includes DJI-specific types:
# .dng (raw stills), .lrv/.lrf (low-res proxy video), .srt (telemetry subtitles).
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".dng", ".tif", ".tiff", ".heic", ".bmp", ".gif"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".mts", ".h264", ".lrv", ".lrf"}
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS

# Category folder names - these mirror the Forensics tab cards.
CAT_FLIGHT = "flight_logs"
CAT_MEDIA = "media"
CAT_OTHER = "other"

# Mountpoints we never treat as a drone data source, even if flagged removable.
SYSTEM_MOUNTS = {"/", "/boot", "/boot/efi", "/home", "/var", "/usr"}

# Read files in 1 MiB chunks when hashing (keeps memory flat on large videos).
HASH_CHUNK_BYTES = 1024 * 1024


def categorize(filename):
    """
    Map a filename to (category, extension) for the downstream modules.

    Returns one of CAT_FLIGHT / CAT_MEDIA / CAT_OTHER and the lowercase ext.
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext in FLIGHT_LOG_EXTS:
        return CAT_FLIGHT, ext
    if ext in MEDIA_EXTS:
        return CAT_MEDIA, ext
    return CAT_OTHER, ext


def _truthy(value):
    """lsblk's `rm`/removable field may be bool, '1'/'0', or 1/0 across versions."""
    return value in (True, 1, "1", "true", "True")


def _safe_name(name):
    """Sanitize a volume label into a filesystem-safe folder name."""
    if not name:
        return "source"
    keep = "-_.() "
    cleaned = "".join(c if (c.isalnum() or c in keep) else "_" for c in str(name))
    cleaned = cleaned.strip().replace(" ", "_")
    return cleaned or "source"


def _project_root():
    """Project root = three levels up from this file (forensics/acquisition/x.py)."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class USBExtractor:
    """
    Wired USB acquisition for INDRA forensics.

    Typical use:
        ex = USBExtractor()                 # defaults to data/extracted/<auto id>
        manifest = ex.extract()             # auto-detect + copy + hash + manifest

        # or point at explicit already-mounted paths (bypasses detection):
        manifest = ex.extract(sources=["/media/user/DJI_SD"])
    """

    def __init__(self, output_root=None, session_id=None):
        # Unique, sortable session id: 20260910_143512_ab12cd
        self.session_id = session_id or (
            datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        )

        base = output_root or os.path.join(_project_root(), "data", "extracted")
        self.output_root = os.path.join(base, self.session_id)

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect_dji_usb(self):
        """
        Return True if a DJI device is visible on the USB bus.

        Best-effort only: in USB mass-storage mode a drone/SD reader may report a
        generic vendor, so a False result does NOT mean "no drone" - it's a hint,
        not a gate. Never raises.
        """
        try:
            out = subprocess.run(
                ["lsusb"], capture_output=True, text=True, timeout=10
            )
        except (FileNotFoundError, OSError, subprocess.SubprocessError) as e:
            log_warn(f"Could not run lsusb ({e}); skipping DJI USB-ID check.")
            return False

        text = (out.stdout or "").lower()
        return (DJI_USB_VENDOR_ID in text) or ("dji" in text)

    def find_usb_storage(self):
        """
        Enumerate mounted USB / removable storage volumes as candidate sources.

        Parses `lsblk -J` (JSON) and keeps volumes that are mounted AND either on
        the USB transport or flagged removable, excluding system mounts. Returns a
        list of source dicts; never raises (returns [] on any failure).
        """
        try:
            out = subprocess.run(
                ["lsblk", "-J", "-o",
                 "NAME,MOUNTPOINT,RM,TRAN,VENDOR,MODEL,LABEL,SIZE,TYPE,FSTYPE"],
                capture_output=True, text=True, timeout=10,
            )
            data = json.loads(out.stdout or "{}")
        except (FileNotFoundError, OSError, subprocess.SubprocessError) as e:
            log_warn(f"Could not run lsblk ({e}); cannot auto-detect USB storage.")
            return []
        except json.JSONDecodeError as e:
            log_warn(f"Could not parse lsblk output ({e}).")
            return []

        sources = []

        def walk(dev, parent_tran=None):
            tran = dev.get("tran") or parent_tran
            mp = dev.get("mountpoint")
            removable = _truthy(dev.get("rm"))
            if mp and mp not in SYSTEM_MOUNTS and not mp.startswith("["):
                if tran == "usb" or removable:
                    sources.append({
                        "device": "/dev/" + (dev.get("name") or ""),
                        "mountpoint": mp,
                        "label": (dev.get("label") or dev.get("model")
                                  or dev.get("name") or "source"),
                        "vendor": (dev.get("vendor") or "").strip(),
                        "model": (dev.get("model") or "").strip(),
                        "size": dev.get("size"),
                        "fstype": dev.get("fstype"),
                        "transport": tran,
                        "removable": removable,
                    })
            for child in dev.get("children") or []:
                walk(child, tran)

        for dev in data.get("blockdevices") or []:
            walk(dev)
        return sources

    # ------------------------------------------------------------------
    # Hashing
    # ------------------------------------------------------------------

    @staticmethod
    def sha256_file(path):
        """SHA-256 of a file, streamed in chunks. Returns hex digest or None."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(HASH_CHUNK_BYTES), b""):
                h.update(chunk)
        return h.hexdigest()

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def extract(self, sources=None):
        """
        Run the full acquisition and return the manifest dict.

        Args:
            sources: optional list of explicit already-mounted paths to extract
                     from. When given, auto-detection is skipped (useful for
                     offline testing with a sample folder or SD card). When None,
                     the host is scanned for a DJI device / USB storage.

        Exit-independent: this method never raises for expected conditions
        (no drone, unreadable file, interrupted copy) - it records them in the
        manifest's `errors` list and keeps going.
        """
        manifest = {
            "tool": "INDRA usb_extractor",
            "schema_version": 1,
            "session_id": self.session_id,
            "host": os.uname().nodename if hasattr(os, "uname") else "",
            "extraction_started": datetime.now(timezone.utc).isoformat(),
            "extraction_completed": None,
            "interrupted": False,
            "dji_device_detected": None,
            "sources": [],
            "files": [],
            "errors": [],
            "summary": {
                "total_files": 0,
                "total_bytes": 0,
                "counts": {CAT_FLIGHT: 0, CAT_MEDIA: 0, CAT_OTHER: 0},
                "error_count": 0,
            },
        }

        # --- Resolve sources: explicit paths, or auto-detect ---
        if sources:
            resolved = []
            for path in sources:
                if os.path.isdir(path):
                    resolved.append({
                        "device": None, "mountpoint": os.path.abspath(path),
                        "label": os.path.basename(os.path.normpath(path)),
                        "vendor": "", "model": "", "size": None,
                        "fstype": None, "transport": "explicit", "removable": None,
                    })
                else:
                    msg = f"--source path is not a directory: {path}"
                    log_err(msg)
                    manifest["errors"].append({"path": path, "error": msg})
            sources = resolved
        else:
            manifest["dji_device_detected"] = self.detect_dji_usb()
            if manifest["dji_device_detected"]:
                log_ok("DJI device detected on USB bus.")
            else:
                log_warn("No DJI USB id seen. If the drone/SD is in mass-storage "
                         "mode it may still appear below as a removable volume.")
            sources = self.find_usb_storage()

        # --- Nothing to do ---
        if not sources:
            log_err("No drone/USB storage found to extract from. "
                    "Connect the drone (or its SD card) via USB and ensure the "
                    "volume is mounted, or pass --source <mounted_path>.")
            manifest["summary"]["error_count"] = len(manifest["errors"])
            manifest["extraction_completed"] = datetime.now(timezone.utc).isoformat()
            self._write_manifest(manifest)
            return manifest

        manifest["sources"] = sources
        log_info(f"Session {self.session_id}: {len(sources)} data source(s) found.")
        for s in sources:
            log_info(f"    - {s['label']} @ {s['mountpoint']} "
                     f"({s.get('fstype') or '?'}, {s.get('size') or '?'})")

        # --- Prepare output tree ---
        try:
            for cat in (CAT_FLIGHT, CAT_MEDIA, CAT_OTHER):
                os.makedirs(os.path.join(self.output_root, cat), exist_ok=True)
        except OSError as e:
            log_err(f"Could not create output directory {self.output_root}: {e}")
            manifest["errors"].append({"path": self.output_root, "error": str(e)})
            manifest["summary"]["error_count"] = len(manifest["errors"])
            manifest["extraction_completed"] = datetime.now(timezone.utc).isoformat()
            return manifest

        # --- Copy each source (interruptible, per-file fault tolerant) ---
        try:
            for source in sources:
                self._copy_source(source, manifest)
        except KeyboardInterrupt:
            manifest["interrupted"] = True
            log_warn("Extraction interrupted by user - writing partial manifest.")

        # --- Finalize ---
        manifest["summary"]["error_count"] = len(manifest["errors"])
        manifest["extraction_completed"] = datetime.now(timezone.utc).isoformat()
        self._write_manifest(manifest)

        s = manifest["summary"]
        log_ok(f"Extraction complete: {s['total_files']} files "
               f"({s['counts'][CAT_FLIGHT]} flight logs, "
               f"{s['counts'][CAT_MEDIA]} media, {s['counts'][CAT_OTHER]} other), "
               f"{s['error_count']} error(s).")
        log_ok(f"Output: {self.output_root}")
        return manifest

    def _copy_source(self, source, manifest):
        """Walk one source volume, copying + hashing every readable file."""
        root = source["mountpoint"]
        if not root or not os.path.isdir(root):
            msg = f"source not accessible / not mounted: {root}"
            log_err(msg)
            manifest["errors"].append({"path": root, "error": msg})
            return

        label = _safe_name(source.get("label"))
        log_info(f"Copying from {root} (label: {label}) ...")

        for dirpath, _dirnames, filenames in os.walk(root):
            for fn in filenames:
                src_file = os.path.join(dirpath, fn)
                try:
                    rel = os.path.relpath(src_file, root)
                    category, ext = categorize(fn)

                    dest_dir = os.path.join(self.output_root, category, label,
                                            os.path.dirname(rel))
                    os.makedirs(dest_dir, exist_ok=True)
                    dest_file = os.path.join(dest_dir, fn)

                    # copy2 preserves mtime/permissions where possible.
                    shutil.copy2(src_file, dest_file)

                    digest = self.sha256_file(dest_file)
                    size = os.path.getsize(dest_file)

                    manifest["files"].append({
                        "original_path": src_file,
                        "copied_path": dest_file,
                        "relative_path": rel,
                        "source_label": label,
                        "category": category,
                        "file_type": ext or "(none)",
                        "size_bytes": size,
                        "sha256": digest,
                        "extracted_at": datetime.now(timezone.utc).isoformat(),
                    })
                    manifest["summary"]["total_files"] += 1
                    manifest["summary"]["total_bytes"] += size
                    manifest["summary"]["counts"][category] += 1

                except PermissionError as e:
                    log_warn(f"Permission denied, skipping: {src_file}")
                    manifest["errors"].append(
                        {"path": src_file, "error": f"permission denied: {e}"})
                except (OSError, shutil.Error) as e:
                    log_warn(f"Could not copy {src_file}: {e}")
                    manifest["errors"].append({"path": src_file, "error": str(e)})

    def _write_manifest(self, manifest):
        """Persist the manifest JSON next to the extracted category folders."""
        try:
            os.makedirs(self.output_root, exist_ok=True)
            manifest_path = os.path.join(self.output_root, "manifest.json")
            with open(manifest_path, "w") as f:
                json.dump(manifest, f, indent=2)
            log_info(f"Manifest written: {manifest_path}")
        except OSError as e:
            log_err(f"Could not write manifest.json: {e}")


# ======================================================================
# Standalone entry point (mirrors how INDRA runs modules as scripts)
# ======================================================================

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="INDRA wired (USB) forensic extraction for DJI drones.")
    parser.add_argument(
        "--source", action="append", metavar="PATH",
        help="Extract from this already-mounted path instead of auto-detecting. "
             "Repeatable. Useful for offline testing without a real drone.")
    parser.add_argument(
        "--output-dir", metavar="DIR",
        help="Base output directory (a <session_id> folder is created inside). "
             "Default: <project>/data/extracted")
    parser.add_argument(
        "--session-id", metavar="ID",
        help="Custom session id (default: timestamp + short random suffix).")
    args = parser.parse_args(argv)

    extractor = USBExtractor(output_root=args.output_dir, session_id=args.session_id)

    try:
        manifest = extractor.extract(sources=args.source)
    except Exception as e:  # last-resort guard: never crash with a bare traceback
        log_err(f"Unexpected failure during extraction: {e}")
        return 1

    # Exit codes: 0 = extracted something, 2 = nothing found, 1 = fatal (above).
    if manifest["summary"]["total_files"] > 0:
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
