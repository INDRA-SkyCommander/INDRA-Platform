# Deauthenticates a drone connection and takes control

from src.utils import sudo_exec

IWCONFIG = "iwconfig"
DHCLIENT = "dhclient"
INTERFACE = "wlan0"

def get_drone() -> list:
    """
    Retrieves data on available drone from host list
    STUB. TO BE IMPLEMENTED.

    target_info = [drone_channel, drone_essid, drone_mac]
    (at least, but not in that order)
    """
    target_info = []

    return target_info

def deauth_drone(drone_channel) -> bool:
    """
    Deauthicates a target drone from its controller.
    STUB. TO BE IMPLEMENTED.
    """
    deauth = False

    print(f"Jumping onto drone's channel {drone_channel}\n")
    sudo_exec(f"{IWCONFIG} {INTERFACE} channel {drone_channel} shell=True")

    return deauth

def skyjack_drone(drone_essid="192.168.10.1", drone_mac="34:D2:62:77:56") -> int:
    """
    Connects to a deathenticated drone.
    STUB. TO BE IMPLEMENTED.
    """    

    print(f"Connecting to drone {drone_mac}")
    sudo_exec(f"{IWCONFIG} {INTERFACE} essid {drone_essid}")

    sudo_exec(f"{DHCLIENT}, -v {INTERFACE}")

    # run control script
    real_time_control()

    # Disconnect from drone

    # exit code
    return 0

def real_time_control() -> int:
    """
    Lets user control the drone in real time using WASD commands.
    STUB. TO BE IMPLEMENTED.
    """

    # Interact with GUI
    # Accept real time WASD input
    # Upon ESC, exit

    # exit code
    return 0

##################
## START MODULE ##
##################

target = get_drone()
disconnected = deauth_drone(target[0])

if disconnected:
    skyjack_drone(target[1], target[2])


