import socket
import threading

# ── Config ────────────────────────────────────────────────────────────────────
AP_INTERFACE       = "wlx9cefd5f754df"
AP_INTERFACE_IP    = "192.168.10.1"   # Card 1 AP IP (phone side)
LISTEN_PORT        = 8889             # Command port phone sends to

DRONE_INTERFACE    = "wlx9cefd5f66998"
DRONE_HOST         = "192.168.10.1"   # Real drone IP
DRONE_PORT         = 8889             # Drone command port

DRONE_STATE_PORT   = 8890             # Drone → client state/telemetry
DRONE_VIDEO_PORT   = 11111            # Drone → client video stream

SO_BINDTODEVICE    = 25
# ─────────────────────────────────────────────────────────────────────────────

phone_addr       = None
phone_lock       = threading.Lock()


# ── Phone-side command socket (card 1, port 8889) ────────────────────────────
phone_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
phone_sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE,
                      AP_INTERFACE.encode() + b'\0')
phone_sock.bind((AP_INTERFACE_IP, LISTEN_PORT))


# ── Drone-side command socket (card 2, fixed src port 8889) ──────────────────
# Bind to port 8889 on card 2 so the drone's reply comes back to a known port.
drone_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
drone_sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE,
                      DRONE_INTERFACE.encode() + b'\0')
drone_sock.bind(("0.0.0.0", DRONE_PORT))   # fixed src port, all interfaces


# ── Drone-side state/telemetry socket (card 2, port 8890) ────────────────────
# Tello pushes ~10 Hz state strings here automatically after SDK init.
state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
state_sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE,
                      DRONE_INTERFACE.encode() + b'\0')
state_sock.bind(("0.0.0.0", DRONE_STATE_PORT))

# Phone-side state socket — deliver telemetry back to phone on 8890
phone_state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
phone_state_sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE,
                             AP_INTERFACE.encode() + b'\0')
phone_state_sock.bind((AP_INTERFACE_IP, DRONE_STATE_PORT))


# ── Drone-side video socket (card 2, port 11111) ─────────────────────────────
video_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
video_sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE,
                      DRONE_INTERFACE.encode() + b'\0')
video_sock.bind(("0.0.0.0", DRONE_VIDEO_PORT))

# Phone-side video socket — deliver stream back to phone on 11111
phone_video_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
phone_video_sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE,
                             AP_INTERFACE.encode() + b'\0')
phone_video_sock.bind((AP_INTERFACE_IP, DRONE_VIDEO_PORT))


# ── Thread functions ──────────────────────────────────────────────────────────

def phone_to_drone():
    """Forward command packets phone → drone, track phone IP dynamically."""
    global phone_addr
    while True:
        data, addr = phone_sock.recvfrom(4096)
        with phone_lock:
            if phone_addr != addr:
                print(f"[INFO] Phone address updated: {addr}")
                phone_addr = addr
        print(f"[P→D] {addr} | {len(data)}B | {data.hex()}")
        drone_sock.sendto(data, (DRONE_HOST, DRONE_PORT))


def drone_to_phone():
    """Forward command responses drone → phone."""
    while True:
        data, addr = drone_sock.recvfrom(4096)
        print(f"[D→P cmd] {addr} | {len(data)}B | {data.hex()}")
        with phone_lock:
            target = phone_addr
        if target is None:
            print("[WARN] No phone connected yet, dropping cmd response")
            continue
        phone_sock.sendto(data, target)


def drone_state_to_phone():
    """Forward telemetry/state packets drone → phone (port 8890)."""
    while True:
        data, addr = state_sock.recvfrom(4096)
        print(f"[D→P state] {addr} | {len(data)}B")
        with phone_lock:
            target = phone_addr
        if target is None:
            continue
        # Send to phone's IP but on the state port
        phone_state_sock.sendto(data, (target[0], DRONE_STATE_PORT))


def drone_video_to_phone():
    """Forward H.264 video stream drone → phone (port 11111)."""
    while True:
        data, addr = video_sock.recvfrom(65536)   # larger buffer for video
        with phone_lock:
            target = phone_addr
        if target is None:
            continue
        phone_video_sock.sendto(data, (target[0], DRONE_VIDEO_PORT))
        # Video is high-bandwidth — skip per-packet logging


# ── Start threads ─────────────────────────────────────────────────────────────
threading.Thread(target=phone_to_drone,      daemon=True).start()
threading.Thread(target=drone_to_phone,      daemon=True).start()
threading.Thread(target=drone_state_to_phone, daemon=True).start()
threading.Thread(target=drone_video_to_phone, daemon=True).start()

print(f"[RELAY] Command  : {AP_INTERFACE_IP}:{LISTEN_PORT}  ↔  {DRONE_HOST}:{DRONE_PORT}")
print(f"[RELAY] Telemetry: :{DRONE_STATE_PORT} passthrough")
print(f"[RELAY] Video    : :{DRONE_VIDEO_PORT} passthrough")
threading.Event().wait()