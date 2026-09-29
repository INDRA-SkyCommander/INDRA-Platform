"""
INDRA Forensics - analysis sub-package.

Analysis passes that run over an extraction session's files (found via its
manifest.json) and produce structured findings the GUI cards display:

    flight_logs    - parse DJI .TXT (readable) / .DAT (binary header) flight logs
    media_metadata - EXIF / image metadata (camera, timestamp, GPS)
    steganography  - scan images for hidden / appended data

These are first-pass, dependency-light analyzers (Python stdlib + Pillow, which
is already present via the GUI). Deeper decoding - notably encrypted DJI .DAT
flight records and professional stego tools - is intentionally left for the
open-source-tools workstream; see each module's notes.
"""

import json


def load_manifest(manifest_path):
    """Load an extraction session's manifest.json."""
    with open(manifest_path) as f:
        return json.load(f)


def files_in_category(manifest, category):
    """Return the manifest file entries in a given category (flight_logs/media/other)."""
    return [e for e in manifest.get("files", []) if e.get("category") == category]


from .flight_logs import analyze_flight_logs        # noqa: E402
from .media_metadata import analyze_media            # noqa: E402
from .steganography import analyze_stego             # noqa: E402
