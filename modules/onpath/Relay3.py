import socket
import threading

# Card 1 — AP side
AP_INTERFACE    = "wlx9cefd5f754df"
AP_INTERFACE_IP = "192.168.10.1"
LISTEN_PORT     = 8889

# Card 2 — Drone side
DRONE_INTERFACE = "wlx9cefd5f66998"
DRONE_HOST      = "192.168.10.1"
DRONE_PORT      = 8889

# Video config — Tello pushes video to whoever sent "streamon", port 11111
VIDEO_PORT      = 7797
PHONE_VIDEO_PORT = 11111  # port on the phone side to forward video to

SO_BINDTODEVICE = 25

phone_addr = None
phone_lock = threading.Lock()

# --- Command sockets (8889) ---
phone_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
phone_sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE,
                      AP_INTERFACE.encode() + b'\0')
phone_sock.bind((AP_INTERFACE_IP, LISTEN_PORT))

drone_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
drone_sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE,
                      DRONE_INTERFACE.encode() + b'\0')
drone_sock.bind(("0.0.0.0", 0))

# --- Video sockets ---
# Listens for video FROM the drone on port 11111
video_recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
video_recv_sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE,
                           DRONE_INTERFACE.encode() + b'\0')
video_recv_sock.bind(("0.0.0.0", VIDEO_PORT))

# Sends video TO the phone on its video port
video_send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
video_send_sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE,
                           AP_INTERFACE.encode() + b'\0')
video_send_sock.bind((AP_INTERFACE_IP, 0))

def phone_to_drone():
    global phone_addr
    while True:
        data, addr = phone_sock.recvfrom(4096)
        with phone_lock:
            if phone_addr != addr:
                print(f"[INFO] Phone address updated: {addr}")
                phone_addr = addr
        print(f"[P->D] {addr} | {len(data)}B | {data.hex()}")
        drone_sock.sendto(data, (DRONE_HOST, DRONE_PORT))

def drone_to_phone():
    while True:
        data, addr = drone_sock.recvfrom(4096)
        print(f"[D->P] {addr} | {len(data)}B | {data.hex()}")
        with phone_lock:
            target = phone_addr
        if target is None:
            print("[WARN] Drone response dropped — no phone connected yet")
            continue
        phone_sock.sendto(data, target)

def video_relay():
    """Forward video stream from drone (11111) -> phone"""
    while True:
        data, addr = video_recv_sock.recvfrom(65535)  # video frames can be large
        print(f"[VID] {len(data)}B from {addr}")
        with phone_lock:
            target = phone_addr
        if target is None:
            continue
        # Send to phone's video port
        video_send_sock.sendto(data, (target[0], PHONE_VIDEO_PORT))

threading.Thread(target=phone_to_drone, daemon=True).start()
threading.Thread(target=drone_to_phone, daemon=True).start()
threading.Thread(target=video_relay, daemon=True).start()

print(f"[*] Command relay: {AP_INTERFACE_IP}:{LISTEN_PORT} <-> {DRONE_HOST}:{DRONE_PORT}")
print(f"[*] Video relay: drone:{VIDEO_PORT} -> phone:{PHONE_VIDEO_PORT}")
threading.Event().wait()