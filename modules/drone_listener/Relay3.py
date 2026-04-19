import socket
import threading

# Card 1 — AP side (phone connects here)
AP_INTERFACE      = "wlx9cefd5f754df"
AP_INTERFACE_IP   = "192.168.10.1"   # This card's IP on the phone-side network
LISTEN_PORT       = 8889

# Card 2 — Client side (connects to drone's AP)
DRONE_INTERFACE   = "wlx9cefd5f66998"
DRONE_HOST        = "192.168.10.1"   # Drone's IP on its own AP network (confirm this)
DRONE_PORT        = 8889

phone_addr = None
phone_lock = threading.Lock()

# Phone-side socket: bound to AP interface
phone_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
SO_BINDTODEVICE = 25
phone_sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE,
                      AP_INTERFACE.encode() + b'\0')
phone_sock.bind((AP_INTERFACE_IP, LISTEN_PORT))

# Drone-side socket: bound to drone interface, ephemeral local port
drone_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
drone_sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE,
                      DRONE_INTERFACE.encode() + b'\0')
drone_sock.bind(("0.0.0.0", 0))  # FIX: bind, not connect; OS picks port

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

threading.Thread(target=phone_to_drone, daemon=True).start()
threading.Thread(target=drone_to_phone, daemon=True).start()

print(f"[*] Relay listening on {AP_INTERFACE_IP}:{LISTEN_PORT}")
print(f"[*] Forwarding to drone at {DRONE_HOST}:{DRONE_PORT}")
threading.Event().wait()