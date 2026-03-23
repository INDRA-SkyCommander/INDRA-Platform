from djitellopy import Tello

#####
# Control Module
#####

tello = Tello()

def connect():
    tello.connect()
    print(f"Battery: {tello.get_battery()}%")

connect()

tello.land()