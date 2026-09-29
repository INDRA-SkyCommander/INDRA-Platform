"""
INDRA Forensics - acquisition sub-package.

Handles getting data OFF a captured drone and onto local disk for the downstream
forensic modules (flight-log parsing, media metadata, steganography, ...) to
consume. Wired (USB) extraction lives in `usb_extractor`; wireless is a separate
future module.
"""

from .usb_extractor import USBExtractor  # re-exported for convenient importing
