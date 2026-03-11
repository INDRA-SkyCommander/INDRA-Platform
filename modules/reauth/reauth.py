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

options_info = scan_info.get("options", {})
interface = options_info.get("interface")

##################
## START MODULE ##
##################

# Reauth attack cmd

# nmcli
sudo_exec(f"nmcli dev wifi connect {target_mac} ifname {interface}")

# @TODO: Mark an interface as being connected to the drone. Add options for disconnection to Main gui