"""
Steganography screening for INDRA forensics.

A lightweight, dependency-free first-pass scan of extracted images for the two
most common ways data is smuggled inside image files:

    1. Data appended after the image's end-of-image marker (JPEG EOI / PNG IEND)
    2. Embedded archive / document file signatures hidden inside the image bytes

This flags *suspicious* images for follow-up; it is not a full stego toolkit.
Deeper analysis (LSB bit-plane extraction, Steghide/zsteg, payload carving) is
the open-source-tools workstream's job. Python standard library only.
"""

import os

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".tif"}

# Signatures of files sometimes hidden inside an image's byte stream.
EMBEDDED_SIGS = {
    b"PK\x03\x04": "ZIP archive",
    b"Rar!\x1a\x07": "RAR archive",
    b"%PDF": "PDF document",
    b"\x37\x7a\xbc\xaf\x27\x1c": "7z archive",
    b"\x1f\x8b\x08": "GZIP stream",
}


def _trailing_bytes(data, ext):
    """
    Bytes present after the image's real end marker (a classic append-stego
    tell), or None if the marker is not found / not applicable.
    """
    if ext in (".jpg", ".jpeg"):
        idx = data.rfind(b"\xff\xd9")            # JPEG End-Of-Image
        if idx != -1:
            return len(data) - (idx + 2)
    elif ext == ".png":
        idx = data.rfind(b"IEND\xae\x42\x60\x82")  # PNG IEND chunk + CRC
        if idx != -1:
            return len(data) - (idx + 8)
    return None


def analyze_stego(manifest_path):
    """
    Scan the image media in a session manifest for hidden-data indicators.

    Returns a dict:
        {"images_scanned": n, "suspicious": m, "findings": [ {per-image flags} ]}.
    """
    from . import load_manifest, files_in_category

    manifest = load_manifest(manifest_path)
    media = files_in_category(manifest, "media")
    findings = []
    scanned = 0
    suspicious = 0

    for e in media:
        path = e.get("copied_path")
        ext = (e.get("file_type") or "").lower()
        if ext not in IMAGE_EXTS or not path or not os.path.exists(path):
            continue

        scanned += 1
        flags = []
        try:
            with open(path, "rb") as f:
                data = f.read()
        except Exception as ex:
            findings.append({"relative_path": e.get("relative_path"),
                             "flags": [f"unreadable: {ex}"]})
            continue

        trailing = _trailing_bytes(data, ext)
        if trailing and trailing > 0:
            flags.append(f"{trailing} bytes appended after image end-marker")

        # Look for embedded archive/document signatures beyond the file header.
        for sig, name in EMBEDDED_SIGS.items():
            pos = data.find(sig, 4)
            if pos != -1:
                flags.append(f"embedded {name} signature at offset {pos}")

        if flags:
            suspicious += 1
            findings.append({"relative_path": e.get("relative_path"), "flags": flags})
        else:
            findings.append({"relative_path": e.get("relative_path"),
                             "flags": ["no obvious hidden data"]})

    return {"images_scanned": scanned, "suspicious": suspicious, "findings": findings}
