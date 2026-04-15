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
target_ssid = target_info.get("raw_string")  # Use SSID, not MAC address
target_mac = target_info.get("mac_address")

options_info = scan_info.get("options", {})
interface = options_info.get("interface")

# Validate inputs
if not target_ssid:
    print("ERROR: No target SSID provided")
    sys.exit(1)

if not interface:
    print("ERROR: No interface provided")
    sys.exit(1)

print(f"[*] Target SSID: {target_ssid}")
print(f"[*] Target MAC: {target_mac}")
print(f"[*] Interface: {interface}")

##################
## START MODULE ##
##################

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
    result = sudo_exec(f"nmcli dev wifi connect '{target_ssid}' ifname {interface}")
    
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
    
    # Launch the controller GUI
    print("[*] Launching controller GUI...")
    controller_path = os.path.join(os.path.dirname(__file__), '..', '..', "src", "gui", "controllerGUI.py")
    
    try:
        # Launch with output capture to see any errors
        process = subprocess.Popen(
            [sys.executable, controller_path], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        print("[+] Controller GUI launched successfully!")
        print(f"[*] GUI Process ID: {process.pid}")
    except Exception as e:
        print(f"[!] ERROR: Could not launch controller GUI: {e}")
        print(f"[!] Controller path: {controller_path}")
        print(f"[!] Python executable: {sys.executable}")
        print("[!] Reauth successful, but GUI launch failed")
        # Don't exit here - reauth was successful even if GUI failed
    
    sys.exit(0)
    
except Exception as e:
    print(f"ERROR: Reauth module failed: {e}")
    sys.exit(1)