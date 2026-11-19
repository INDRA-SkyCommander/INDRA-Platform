#!/usr/bin/env python3
"""
DJI Tello EDU Passive Video Capture Script (Linux Monitor Mode)
Run with: sudo python3 tello_sniffer_psp.py
"""

import csv
import glob
import os
import shutil
import signal
import subprocess
import sys
import time

REQUIRED_TOOLS = ["airmon-ng", "airodump-ng", "iw", "ip", "tshark", "ffmpeg"]
SCAN_PREFIX = "/tmp/tello_scan"
OUTPUT_PCAP = "tello_stream.pcapng"
RAW_H264 = "raw_stream.h264"
OUTPUT_MP4 = "drone_flight_output.mp4"
VIDEO_PORT = 11111
# tshark field holding the undissected UDP payload. If you get no payloads,
# try "udp.payload" (newer tshark versions).
TSHARK_PAYLOAD_FIELD = "data"


def run(cmd, check=False):
    """Run a command silently (equivalent of `cmd > /dev/null 2>&1`)."""
    return subprocess.run(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=check
    )


def die(msg, code=1):
    print(msg)
    sys.exit(code)


def check_environment():
    if os.geteuid() != 0:
        die("[-] Please run this script with sudo.")

    for tool in REQUIRED_TOOLS:
        if shutil.which(tool) is None:
            die(
                f"[-] Error: Required tool '{tool}' is not installed.\n"
                "    Please install aircrack-ng, wireshark (tshark) and ffmpeg."
            )


def detect_interface():
    """Find a wireless interface (any interface with a /sys/.../wireless dir)."""
    for name in sorted(os.listdir("/sys/class/net")):
        if os.path.isdir(f"/sys/class/net/{name}/wireless"):
            return name

    iface = input(
        "[?] Please enter your Wi-Fi interface name manually (e.g., wlan0): "
    ).strip()
    if not iface:
        die("[-] No interface given.")
    return iface


def enable_monitor_mode(iface):
    print("[+] Disabling conflicting network managers...")
    run(["airmon-ng", "check", "kill"])
    time.sleep(1)

    print(f"[+] Putting {iface} into Monitor Mode...")
    run(["ip", "link", "set", iface, "down"])
    run(["iw", iface, "set", "monitor", "control"])
    run(["ip", "link", "set", iface, "up"])


def is_monitor(iface):
    out = subprocess.run(
        ["iw", "dev", iface, "info"], capture_output=True, text=True
    ).stdout
    return "type monitor" in out


def restore_managed_mode(iface):
    print(f"\n[+] Restoring managed mode on {iface}...")
    run(["ip", "link", "set", iface, "down"])
    run(["iw", iface, "set", "type", "managed"])
    run(["ip", "link", "set", iface, "up"])
    run(["systemctl", "restart", "NetworkManager"])


def scan_for_tello(iface, seconds=10):
    print(f"[+] Scanning for DJI Tello EDU drones... Please wait {seconds} seconds.")
    print("[*] Ensure your drone is turned ON.")

    # Remove stale scan files so we never read an old one
    for old in glob.glob(f"{SCAN_PREFIX}*.csv"):
        os.remove(old)

    proc = subprocess.Popen(
        ["airodump-ng", "--output-format", "csv", "-w", SCAN_PREFIX, iface],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(seconds)
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    scan_files = glob.glob(f"{SCAN_PREFIX}*.csv")
    if not scan_files:
        die("[-] Scan failed or no networks detected.")
    scan_file = max(scan_files, key=os.path.getmtime)

    # airodump CSV: AP section first, blank line, then the Station section.
    # AP columns: 0=BSSID, 3=channel, 13=ESSID
    with open(scan_file, newline="", errors="replace") as f:
        for row in csv.reader(f, skipinitialspace=True):
            if not row:
                continue
            if row[0].startswith("Station MAC"):
                break  # reached the client section
            if len(row) < 14:
                continue
            essid = row[13].strip()
            if essid.upper().startswith(("TELLO-", "RMTT-")):
                return {
                    "bssid": row[0].strip(),
                    "channel": int(row[3].strip()),
                    "essid": essid,
                }
    return None


def record_pcap(iface):
    print(f"[+] Recording UDP port {VIDEO_PORT} packets to {OUTPUT_PCAP}...")
    print("[*] Press Ctrl+C when you are done flying to stop recording and extract the video.")

    # start_new_session=True keeps tshark out of the terminal's Ctrl+C, so we
    # can stop it cleanly ourselves (exactly one SIGINT).
    tshark = subprocess.Popen(
        ["tshark", "-i", iface, "-f", f"udp port {VIDEO_PORT}", "-w", OUTPUT_PCAP, "-q"],
        start_new_session=True,
    )
    try:
        while tshark.poll() is None:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass

    if tshark.poll() is None:
        tshark.send_signal(signal.SIGINT)
    try:
        tshark.wait(timeout=10)
    except subprocess.TimeoutExpired:
        tshark.kill()


def extract_h264():
    print("\n[+] Processing PCAP to extract raw H.264 video bytes...")
    print(f"[*] Carving UDP payloads from port {VIDEO_PORT}...")

    result = subprocess.run(
        [
            "tshark", "-r", OUTPUT_PCAP,
            "-Y", f"udp.port == {VIDEO_PORT}",
            "-T", "fields", "-e", TSHARK_PAYLOAD_FIELD,
        ],
        capture_output=True,
        text=True,
    )
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    if not lines:
        die(f"[-] No UDP payloads found on port {VIDEO_PORT}.")

    print(f"[+] Parsing {len(lines)} UDP payloads...")

    buffer = bytearray()
    packet_count = 0
    for line in lines:
        hexdata = line.strip().replace(":", "")
        try:
            raw = bytes.fromhex(hexdata)
        except ValueError:
            continue

        # Tello video payload: 2-byte header (seq + subseq), then H.264 data.
        if len(raw) <= 2:
            continue

        buffer.extend(raw[2:])
        packet_count += 1

    with open(RAW_H264, "wb") as out:
        out.write(buffer)

    print(f"[+] Stripped 2-byte headers from {packet_count} packets.")
    print(f"[+] Wrote {len(buffer)} bytes to {RAW_H264}")

    if not buffer:
        print("[-] No video data assembled. Ensure capture started before 'streamon'.")
        die("[-] Failed to assemble H.264 data.")


def remux_to_mp4():
    print("[+] Remuxing to MP4 container using FFmpeg...")
    # Raw H.264 has no timestamps, so specify the ~30 fps input rate.
    result = subprocess.run(
        ["ffmpeg", "-y", "-framerate", "30", "-i", RAW_H264, "-c:v", "copy", OUTPUT_MP4],
        capture_output=True,
        text=True,
    )
    print("\n".join(result.stderr.strip().splitlines()[-3:]))  # like `| tail -3`

    if os.path.isfile(OUTPUT_MP4) and os.path.getsize(OUTPUT_MP4) > 0:
        print("\n[======== SUCCESS ========]")
        print(f"[+] Final video saved as: {OUTPUT_MP4}")
    else:
        print(f"[-] FFmpeg remuxing failed. You can inspect '{RAW_H264}' directly.")


def main():
    check_environment()

    iface = detect_interface()
    print(f"[+] Using wireless interface: {iface}")

    monitor_enabled = False
    try:
        enable_monitor_mode(iface)
        monitor_enabled = True  # set before the check so cleanup still restores

        if not is_monitor(iface):
            die(f"[-] Failed to set {iface} to Monitor Mode.")
        print("[+] Monitor Mode successfully enabled.")

        tello = scan_for_tello(iface)
        if tello is None:
            die("[-] No DJI Tello drone found in the airspace.")

        print("[+] Found Tello Drone!")
        print(f"    - SSID:    {tello['essid']}")
        print(f"    - BSSID:   {tello['bssid']}")
        print(f"    - Channel: {tello['channel']}")

        print(f"[+] Locking interface {iface} onto Channel {tello['channel']}...")
        run(["iw", "dev", iface, "set", "channel", str(tello["channel"])])

        print()
        print("==============================================================================")
        print(f" STEP 1: Connect your phone to the Tello Wi-Fi ({tello['essid']}).")
        print(" STEP 2: Open the Tello App and start the live video feed.")
        print(" STEP 3: Return here and press [ENTER] to start recording.")
        print(" NOTE:   Capture MUST begin before (or at the same moment as) 'streamon'.")
        print("         If you start late, SPS/PPS/IDR are missed and the H.264 is unplayable.")
        print("==============================================================================")
        input()

        record_pcap(iface)
        extract_h264()
        remux_to_mp4()

    finally:
        # Equivalent of `trap cleanup EXIT`
        if monitor_enabled:
            restore_managed_mode(iface)


if __name__ == "__main__":
    main()
