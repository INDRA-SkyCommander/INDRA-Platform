"""License.

Copyright 2018 PingguSoft <pinggusoft@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
import os
import sys
import json
import time
import keyboard
import tello
import subprocess

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Direct import to avoid circular dependency with GUI
def sudo_exec(cmd: str):
    """
    Executes a command with sudo privileges.
    """
    print(f"Running: sudo {cmd}")
    return subprocess.run(f"sudo {cmd}", shell=True)

###############################################################################
# constants
###############################################################################
KEY_MASK_UP    = 0x0001
KEY_MASK_DOWN  = 0x0002
KEY_MASK_LEFT  = 0x0004
KEY_MASK_RIGHT = 0x0008
KEY_MASK_W     = 0x0010
KEY_MASK_S     = 0x0020
KEY_MASK_A     = 0x0040
KEY_MASK_D     = 0x0080
KEY_MASK_SPC   = 0x0100
KEY_MASK_1     = 0x0200
KEY_MASK_2     = 0x0400
KEY_MASK_ESC   = 0x8000

RC_VAL_MIN     = 364
RC_VAL_MID     = 1024
RC_VAL_MAX     = 1684

IDX_ROLL       = 0
IDX_PITCH      = 1
IDX_THR        = 2
IDX_YAW        = 3

###############################################################################
# global variables
###############################################################################
mKeyFlags    = 0
mOldKeyFlags = 0
mRCVal       = [1024, 1024, 1024, 1024]


###############################################################################
# functions
###############################################################################
def isKeyPressed(mask):
    if mKeyFlags & mask == mask:
        return True
    return False

def isKeyToggled(mask):
    if (mKeyFlags & mask) != (mOldKeyFlags & mask):
        return True
    return False

def setFlag(e, mask):
    global mKeyFlags
    if e.event_type == 'down':
        mKeyFlags = mKeyFlags | mask
    else:
        mKeyFlags = mKeyFlags & ~mask

def toggleFlag(e, mask):
    global mKeyFlags
    if e.event_type == 'up':
        if mKeyFlags & mask == mask:
            mKeyFlags = mKeyFlags & ~mask
        else:
            mKeyFlags = mKeyFlags | mask

def clearToggle():
    global mOldKeyFlags
    mOldKeyFlags = mKeyFlags

tblKeyFunctions = {
#    key      toggle   mask
    'up'    : (False, KEY_MASK_UP),
    'down'  : (False, KEY_MASK_DOWN),
    'left'  : (False, KEY_MASK_LEFT),
    'right' : (False, KEY_MASK_RIGHT),
    'w'     : (False, KEY_MASK_W),
    's'     : (False, KEY_MASK_S),
    'a'     : (False, KEY_MASK_A),
    'd'     : (False, KEY_MASK_D),
    'esc'   : (False, KEY_MASK_ESC),
    'space' : (True,  KEY_MASK_SPC),
    '1'     : (True,  KEY_MASK_1),
    '2'     : (True,  KEY_MASK_2),
}

def handleKey(e):
    global mKeyFlags
    if e.name in tblKeyFunctions:
        if tblKeyFunctions[e.name][0] == False:
            setFlag(e, tblKeyFunctions[e.name][1])
        else:
            toggleFlag(e, tblKeyFunctions[e.name][1])

def load_selected_target():
    target_data_file = os.path.join(
        os.path.dirname(__file__), '..', '..', "data", "module_input_data.json"
    )
    with open(target_data_file, 'r') as f:
        scan_info = json.load(f)
    target_name = scan_info.get("target_name", "")
    target_info = scan_info.get("target_info", {})
    options = scan_info.get("options", {})

    interface = options.get("interface", "wlan0")
    ssid = target_info.get("raw_string", "").strip()
    
    if not ssid or ssid == "N/A":
        if " - " in target_name.strip():
            ssid = target_name.split(" - ")[0].strip() 
    
    # For our testing, tello's wifi should always be open w/ no password
    encryption = target_info.get("encryption", "Open").strip()
    password = options.get("wifi_password", "").strip()

    return interface, ssid, encryption, password

def authenticate_to_target(interface: str, ssid: str, encryption: str, password: str = "") -> bool:
    if not interface or not ssid:
        print("[AUTH] Missing interface or SSID.")
        return False
    
    print(f"[AUTH] Prepareing {interface} in managed mode...")
    sudo_exec(f"ip link set {interface} down")
    sudo_exec(f"iw {interface} set type managed")
    sudo_exec(f"ip link set {interface} up")
    time.sleep(1)

    if encryption.lower().startswith("open"):
        print(f"[AUTH] Connecting to open network: {ssid}")
        result = sudo_exec(f'iw dev {interface} connect {ssid}')
        return getattr(result,"returncode", 1) == 0
    
    if not password:
        print(f"[AUTH] Target '{ssid}' is secured ({encryption}) but no password was provided.")
        return False
    print(f"[AUTH] Connecting to secured network {ssid}")
    result = sudo_exec(f'nmcli dev wifi connect "{ssid}" password "{password}" ifname {interface}')
    return getattr(result, "returncode", 1) == 0

###############################################################################
# main
###############################################################################

# Authenticate to the tello drone
# iface, ssid, enc, pwd = load_selected_target()
# if not authenticate_to_target(iface, ssid, enc, pwd):
#     raise SystemExit("[AUTH] Failed to authenticate/connect to selected target. Aborting.")

print('Tello Controller                      ')
print('+------------------------------------+')
print('|  ESC(quit) 1(360) 2(bounce)        |')
print('+------------------------------------+')
print('|                                    |')
print('|      w                   up        |')
print('|  a       d          left    right  |')
print('|      s                  down       |')
print('|                                    |')
print('|         space(takeoff/land)        |')
print('|                                    |')
print('+------------------------------------+')

mDrone = tello.Tello()
keyboard.hook(handleKey)

while True:
    if isKeyPressed(KEY_MASK_ESC):
        break;
    
    # Toggle Keys
    if isKeyToggled(KEY_MASK_SPC):
        if isKeyPressed(KEY_MASK_SPC):
            mDrone.takeOff()
            print('take off')
        else:
            mDrone.land()
            print('land')
        clearToggle()

    if isKeyToggled(KEY_MASK_1):
        if isKeyPressed(KEY_MASK_1):
            mDrone.setSmartVideoShot(tello.Tello.TELLO_SMART_VIDEO_360, True)
            print('SmartVideo 360 start')
        else:
            mDrone.setSmartVideoShot(tello.Tello.TELLO_SMART_VIDEO_360, False)
            print('SmartVideo 360 stop')
        clearToggle()
        
    if isKeyToggled(KEY_MASK_2):
        if isKeyPressed(KEY_MASK_2):
            mDrone.bounce(True)
            print('Bounce start')
        else:
            mDrone.bounce(False)
            print('Bounce stop')
        clearToggle()
        
    # RC Keys
    # pitch / roll
    if isKeyPressed(KEY_MASK_RIGHT):
        mRCVal[IDX_ROLL] = RC_VAL_MAX
    elif isKeyPressed(KEY_MASK_LEFT):
        mRCVal[IDX_ROLL] = RC_VAL_MIN
    else:
        mRCVal[IDX_ROLL] = RC_VAL_MID
        
    if isKeyPressed(KEY_MASK_UP):
        mRCVal[IDX_PITCH] = RC_VAL_MAX
    elif isKeyPressed(KEY_MASK_DOWN):
        mRCVal[IDX_PITCH] = RC_VAL_MIN
    else:
        mRCVal[IDX_PITCH] = RC_VAL_MID
      
    # thr / yaw
    if isKeyPressed(KEY_MASK_W):
        mRCVal[IDX_THR] = RC_VAL_MAX
    elif isKeyPressed(KEY_MASK_S):
        mRCVal[IDX_THR] = RC_VAL_MIN
    else:
        mRCVal[IDX_THR] = RC_VAL_MID
        
    if isKeyPressed(KEY_MASK_D):
        mRCVal[IDX_YAW] = RC_VAL_MAX
    elif isKeyPressed(KEY_MASK_A):
        mRCVal[IDX_YAW] = RC_VAL_MIN
    else:
        mRCVal[IDX_YAW] = RC_VAL_MID        
    
    mDrone.setStickData(0, mRCVal[IDX_ROLL], mRCVal[IDX_PITCH], mRCVal[IDX_THR], mRCVal[IDX_YAW])
    #print 'roll:{0:4d}, pitch:{1:4d}, thr:{2:4d}, yaw:{3:4d}'.format(mRCVal[IDX_ROLL], mRCVal[IDX_PITCH], mRCVal[IDX_THR], mRCVal[IDX_YAW])
    
mDrone.stop()
