#UDP communication
import socket
#So we can have bi-directional communication 
import threading

# Config Card 1 
AP_INTERFACE_IP = "192.168.0.1" #Card 1's AP IP address
LISTEN_PORT = 8889 #Port that phone sends commands to

DRONE_HOST = "192.168.10.1" # Real Drone's IP address
DRONE_PORT = 8889 #Drone's command port


#Starts as None and will dynamically change as the phone connects 
phone_addr = None
#Mutex preventing both threads writing or reading (anti-race-cond)
phone_lock = threading.Lock()


#Creats the UDP socket(8889) and binds it to the AP_INTERFACE_IP
#it will only accept traffic from card 1 
phone_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
phone_sock.bind((AP_INTERFACE, LISTEN_PORT))


#Creates another UDP port on the drone side binds to (0.0.0.0)!!!!!(this may need to change to card 2's IP to make sure it sends through it)
drone_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
drone_sock.connect(("0.0.0.0", LISTEN_PORT + 1)) #ephemeral local port for drone side 

def phone_to_drone(): 
    """Forward packets from phone -> drone, track phones IP dynamically"""
    global phone_addr
    while True:
        data, addr = phone_sock.recvfrom(4096)
        with phone_lock:
            if phone_addr != addr
        print(f"[INFO] Phone address updated: {addr}")
        phone_addr = addr # ---> This is where we are updating the phone IP everytime there is a com
    print(f"[P->D] {addr} | {len(data)} bytes | {data.hex()}") # Logging the packets (src|byte count|raw hex)
    drone_sock.sendto(data, (DRONE_HOST, DRONE_PORT)) #pass it unchanged to the drone 


def drone_to_phone(): 
    """Forward packets from drone -> phone, drop if phone hasnt connected yet"""
    while True: 
        data, addr = drone_sock.recvfrom(4096)
        print(f"[D->P] {addr} | {len(data)} bytes | {data.hex()}") #Logging same as before 
        with phone_lock: 
            target = phone_addr 
        if target is None:
            print("[WARN] Drone sent data but no phone connected yet, dropping")
            continue 
        phone_sock.sendto(data, target) #pass unchanged 


#Starts both functions at the same time on seperate threads
threading.Thread(target=phone_to_drone, daemon=True).start()
threading.Thread(target=drone_to_phone, deamon-True).start()

print(f"Relay Listening on {AP_INTERFACE_IP}:{LISTEN_PORT}")
print(f"Forwarding to drone at {DRONE_HOST}:{DRONE_PORT}")
threading.Event().wait()
