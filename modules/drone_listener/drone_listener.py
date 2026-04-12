import socket
import json
import os
import sys
import struct
from responses import make_conn_ack, make_date_time_response, make_status_response
from protocol import parse_packet

# ========================
# Read module input data (eventually from JSON, hardcoded for now)
# ========================

data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
# json_path = os.path.join(data_dir, 'module_input_data.json')

# with open(json_path, 'r') as f:
#     data = json.load(f)

# interface = data.get("options", {}).get("interface", "0.0.0.0")
# target_name = data.get("target_name", "Unknown")
target_name =  "iPhone"
interface = "wlx9cefd5f754df"

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8889
PHONE_CMD_PORT = 7777

# ========================
# START LISTENER
# ========================`

print(f"[*] Drone listener starting on {LISTEN_HOST}:{LISTEN_PORT}")
print(f"[*] Intercepting commands for target: {target_name}")

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

try:
    server.bind((LISTEN_HOST, LISTEN_PORT))
except OSError as e:
    print(f"[!] Failed to bind to port {LISTEN_PORT}: {e}")
    sys.exit(1)

print(f"[*] Listening for drone controller on port {LISTEN_PORT}...")

intercepted = []

try:
    while True:
        raw, addr = server.recvfrom(1024)
        phone_ip = addr[0]
        
        # Plaintext conn_req
        if raw.startswith(b"conn_req:"):
            print(f"[<] {addr[0]} -> TEXT: '{raw.decode()}'")
            server.sendto(make_conn_ack(), (phone_ip, PHONE_CMD_PORT))
            print(f"[>] {addr[0]} <- TEXT: 'conn_ack:g+'")
            continue

        # Binary packet
        parsed = parse_packet(raw)
        parsed["from_ip"] = addr[0]
        
        cmd_id = parsed.get("cmd_id")
        seq_id = parsed.get("seq_id")

        if parsed["type"] == "text":
            print(f"[<] {addr[0]} -> TEXT: '{parsed['raw']}'")

        elif parsed["cmd_name"] == "STICK":
            s = parsed.get("stick", {})
            print(f"[<] {addr[0]} -> STICK: roll={s['roll']} pitch={s['pitch']} throttle={s['throttle']} yaw={s['yaw']} fast_mode={s['fast_mode']}")
            server.sendto(make_status_response(seq_id), (phone_ip, PHONE_CMD_PORT))
            print(f"[>] {addr[0]} <- STATUS response")
        
        elif parsed["cmd_name"] == "DATE_TIME":
            print(f"[<] {addr[0]} -> DATE_TIME request: (seq:{seq_id})")
            server.sendto(make_date_time_response(seq_id), (phone_ip, PHONE_CMD_PORT))
            print(f"[>] {addr[0]} <- DATE_TIME response")

        else:
            print(f"[<] {addr[0]} -> {parsed['direction']} CMD: {parsed['cmd_name']} (ID: {parsed['cmd_id']}, Seq: {parsed['seq_id']}) Payload: {parsed['payload']}")

        intercepted.append(parsed)

except KeyboardInterrupt:
    print("\n[*] Listener interrupted.")

finally:
    # Dump all intercepted commands to data dir
    # out_path = os.path.join(data_dir, 'intercepted_commands.json')
    # with open(out_path, 'w') as f:
    #     json.dump(intercepted, f, indent=4)
    # print(f"[*] Intercepted {len(intercepted)} commands saved to {out_path}")
    server.close()
    sys.exit(0)