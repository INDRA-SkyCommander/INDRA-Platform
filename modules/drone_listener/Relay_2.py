import threading
import logging
from scapy.all import *


logging.basicConfig(level=logging.INFO, format="[%(threadName)s] %(message)s")
log = logging.getLogger(__name__)

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
        try:
            data, addr = state_sock.recvfrom(4096)
            with phone_lock:
                target = phone_addr
            if target is None:
                continue

            log.debug(f"[D→P state] {len(data)}B → spoofed dst={SPOOF_DST_TO_PHONE}:{STATE_PORT}")

            send_raw(
                iface=AP_INTERFACE,
                src_ip=addr[0],             # drone's real IP as source
                dst_ip=SPOOF_DST_TO_PHONE,  # fixed spoofed destination
                src_port=STATE_PORT,
                dst_port=STATE_PORT,
                data=data
            )
        except Exception as e:
            log.error(f"drone_state_to_phone error: {e}")


# ── Launch ────────────────────────────────────────────────────────────────────
threads = [
    ("phone_to_drone",       phone_to_drone),
    ("drone_to_phone_cmd",   drone_to_phone_cmd),
    ("drone_video_to_phone", drone_video_to_phone),
    ("drone_state_to_phone", drone_state_to_phone),
]

for name, fn in threads:
    threading.Thread(target=fn, name=name, daemon=True).start()

log.info(f"Relay active | spoof src→drone={SPOOF_SRC_TO_DRONE} | spoof dst→phone={SPOOF_DST_TO_PHONE}")
log.info(f"Ports -- cmd:{CMD_PORT}  state:{STATE_PORT}  video:{VIDEO_PORT}")
threading.Event().wait()
