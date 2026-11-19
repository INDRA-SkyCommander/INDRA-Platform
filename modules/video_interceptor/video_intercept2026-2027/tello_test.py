import socket
import time
import threading

#tello network info
TELLO_IP = "192.168.10.1"
COMMAND_PORT = 8889
TELEMETRY_PORT = 22222

# Create a UDP socket for sending commands and receiving command responses
command_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# Bind to a local port on your machine to listen for responses
command_socket.bind(('', 9000)) 

# Create a UDP socket to listen to the drone's telemetry stream
telemetry_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
telemetry_socket.bind(('', TELEMETRY_PORT))

def receive_commands():
    """Background thread to listen for 'OK' or 'error' responses from the drone."""
    while True:
        try:
            data, server = command_socket.recvfrom(1024)
            print(f"[Drone Response]: {data.decode(encoding='utf-8').strip()}")
        except Exception as e:
            print(f"Command receive error: {e}")
            break

def receive_telemetry():
    """Background thread to listen to the continuous flight status data."""
    while True:
        try:
            data, server = telemetry_socket.recvfrom(1024)
            # Un-comment the line below if you want to print the live status to your console
            # print(f"[Telemetry]: {data.decode(encoding='utf-8').strip()}")
        except Exception as e:
            print(f"Telemetry receive error: {e}")
            break

def send_command(command: str):
    """Helper function to format and send text commands to the drone."""
    print(f"[Sending Command]: {command}")
    command_socket.sendto(command.encode(encoding='utf-8'), (TELLO_IP, COMMAND_PORT))

# Start background threads so receiving data doesn't block our main script execution
threading.Thread(target=receive_commands, daemon=True).start()
threading.Thread(target=receive_telemetry, daemon=True).start()

try:
    # 1. Put the drone into SDK Command Mode (Crucial first step)
    send_command("command")
    time.sleep(2) # Give the drone a moment to process and return "OK"

    # 2. Tell the drone to turn on its video transmitter
    send_command("streamon")
    time.sleep(2)

    print("\n--> Stream should now be active! Start Wireshark or your PCAP capture tool now.")
    print("--> Look for a flood of traffic coming from the drone to UDP Port 11111.")
    print("--> Press Ctrl+C in this terminal when you want to stop the stream and exit.\n")

    # Keep the script alive so the video stream stays open
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\nShutting down stream...")
    # Clean up by telling the drone to turn off the video feed to save battery
    send_command("streamoff")
    time.sleep(1)
    command_socket.close()
    telemetry_socket.close()
    print("Program exited safely.")
