import socket
import json
import os
import sys

# ========================
# Read module input data
# ========================

data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
json_path = os.path.join(data_dir, 'module_input_data.json')

with open(json_path, 'r') as f:
    data = json.load(f)

interface = data.get("options", {}).get("interface", "0.0.0.0")
target_name = data.get("target_name", "Unknown")

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8889

# ========================
# Known Tello SDK commands
# ========================

DRONE_COMMANDS = {
    "command":        "SDK mode init",
    "takeoff":        "Drone taking off",
    "land":           "Drone landing",
    "emergency":      "EMERGENCY STOP",
    "streamon":       "Video stream ON",
    "streamoff":      "Video stream OFF",
    "flip":           "Flip maneuver",
    "up":             "Ascending",
    "down":           "Descending",
    "left":           "Moving left",
    "right":          "Moving right",
    "forward":        "Moving forward",
    "back":           "Moving backward",
    "cw":             "Rotating clockwise",
    "ccw":            "Rotating counter-clockwise",
    "speed":          "Speed set",
    "battery?":       "Battery query",
    "speed?":         "Speed query",
    "time?":          "Flight time query",
    "wifi?":          "WiFi SNR query",
    "sdk?":           "SDK version query",
    "sn?":            "Serial number query",
}

def parse_command(raw):
    """
    Parses a raw drone command string and returns a human-readable label.
    Handles both bare commands and commands with arguments (e.g. 'up 50').
    """
    raw = raw.strip().lower()
    base = raw.split()[0] if raw else ""

    if base in DRONE_COMMANDS:
        label = DRONE_COMMANDS[base]
        args = raw[len(base):].strip()
        return f"{label} {f'-> args: {args}' if args else ''}"
    
    return f"Unknown command: '{raw}'"

# ========================
# Start listener
# ========================

print(f"[*] Drone listener starting on {LISTEN_HOST}:{LISTEN_PORT}")
print(f"[*] Intercepting commands for target: {target_name}")

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

try:
    server.bind((LISTEN_HOST, LISTEN_PORT))
except OSError as e:
    print(f"[!] Failed to bind to port {LISTEN_PORT}: {e}")
    sys.exit(1)

server.listen(5)
print(f"[*] Listening for drone controller on port {LISTEN_PORT}...")

intercepted = []

try:
    while True:
        conn, addr = server.accept()
        print(f"[+] Controller connected from {addr[0]}:{addr[1]}")

        try:
            while True:
                raw = conn.recv(1024)
                if not raw:
                    print(f"[-] Controller at {addr[0]} disconnected.")
                    break

                decoded = raw.decode(errors='replace').strip()
                parsed  = parse_command(decoded)

                intercepted.append({
                    "from": addr[0],
                    "raw":  decoded,
                    "parsed": parsed
                })

                print(f"[<] {addr[0]} -> RAW: '{decoded}' | PARSED: {parsed}")

                # Forward an OK back so the controller stays alive
                try:
                    conn.sendall(b"ok\r\n")
                except Exception:
                    pass

        except Exception as e:
            print(f"[!] Connection error: {e}")
        finally:
            conn.close()

except KeyboardInterrupt:
    print("\n[*] Listener interrupted.")

finally:
    # Dump all intercepted commands to data dir
    out_path = os.path.join(data_dir, 'intercepted_commands.json')
    with open(out_path, 'w') as f:
        json.dump(intercepted, f, indent=4)
    print(f"[*] Intercepted {len(intercepted)} commands saved to {out_path}")
    server.close()
    sys.exit(0)