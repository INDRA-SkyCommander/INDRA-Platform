import os
import json
import base64
from scapy.all import sniff, Raw

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

options_info = scan_info.get("options", {})
packets = options_info.get("packets")
interface = options_info.get("interface")

output_data_file = os.path.join(os.path.dirname(__file__), '..', '..', "data", "sniff_output.log")

protocol = "udp" # UDP/TCP
direction = "src port" # Sniffing packets outgoing FROM the port
port = None # Port to sniff

### FIND THE ABOVE VALUES FOR TELLO DRONES
### CONFIRM THAT THEY WORK ON TARGET

bpf_filter = f"{protocol} {direction} {port}"

def packet_handler(packet):
    """
    Extracts raw payload, base64 encodes it, and writes to file.
    """

    if packet.haslayer(Raw):
        try:
            # Extract binary
            raw_data = packet[Raw].load

            b64_data = base64.b64encode(raw_data).decode('utf-8')

            log_entry = f"{b64_data}\n"

            with open(output_data_file, 'a') as f:
                f.write(log_entry)
                f.flush()

            print(f"Captured {len(raw_data)} bytes from {target_mac}.")
        except Exception as e:
            print(f"Error processing packet: {e}")

##################
## START MODULE ##
##################

print(f"Started sniffing with filter: {bpf_filter}\n")

try:
    sniff(iface=interface,
          filter=bpf_filter,
          prn=packet_handler,
          timeout=packets,
          store=0 # Causes RAM issues if you store
        )
    print("Sniffing complete.\n")
except Exception as e:
    print(f"Sniffer crashed: {e}")
