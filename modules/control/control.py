"""
DJI Tello Edu Drone Control Module
Provides reusable TelloController class for drone flight operations.

Note: For the complete GUI interface, use src.gui.controllerGUI which includes
the TelloController class along with a full flight deck interface.
"""

from djitellopy import Tello


class TelloController:
    """
    Manages DJI Tello Edu drone connections and flight operations.
    Provides methods for basic flight control.
    """
    
    def __init__(self):
        self.tello = None
        self.is_connected = False
        self.is_flying = False
        self.speed = 50  # 0-100 cm/s
        
    def connect(self):
        """Establish connection to the drone."""
        try:
            self.tello = Tello()
            self.tello.connect()
            battery = self.tello.get_battery()
            self.is_connected = True
            return True, f"Connected! Battery: {battery}%"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
    
    def disconnect(self):
        """Safely disconnect from the drone."""
        try:
            if self.is_flying:
                self.land()
            if self.tello:
                self.tello.end()
            self.is_connected = False
            self.tello = None
            return True, "Disconnected successfully"
        except Exception as e:
            return False, f"Disconnection failed: {str(e)}"
    
    def get_battery(self):
        """Get current battery percentage."""
        if not self.is_connected:
            return None
        try:
            return self.tello.get_battery()
        except Exception:
            return None
    
    def set_speed(self, speed):
        """Set flight speed (0-100 cm/s)."""
        self.speed = max(10, min(100, int(speed)))
        if self.is_connected:
            self.tello.set_speed(self.speed)
    
    # Flight Control Methods
    def takeoff(self):
        """Initiate takeoff."""
        if not self.is_connected:
            return False, "Not connected to drone"
        try:
            self.tello.takeoff()
            self.is_flying = True
            return True, "Takeoff initiated"
        except Exception as e:
            return False, f"Takeoff failed: {str(e)}"
    
    def land(self):
        """Land the drone."""
        if not self.is_connected:
            return False, "Not connected to drone"
        try:
            self.tello.land()
            self.is_flying = False
            return True, "Landing initiated"
        except Exception as e:
            return False, f"Landing failed: {str(e)}"
    
    def emergency_stop(self):
        """Emergency stop - immediately cut motors."""
        if not self.is_connected:
            return False, "Not connected to drone"
        try:
            self.tello.emergency()
            self.is_flying = False
            return True, "Emergency stop activated"
        except Exception as e:
            return False, f"Emergency stop failed: {str(e)}"
    
    # Movement Methods
    def move_forward(self, distance=20):
        """Move forward."""
        if not self.is_flying:
            return False, "Drone not flying"
        try:
            self.tello.move_forward(distance)
            return True, f"Moving forward {distance}cm"
        except Exception as e:
            return False, str(e)
    
    def move_backward(self, distance=20):
        """Move backward."""
        if not self.is_flying:
            return False, "Drone not flying"
        try:
            self.tello.move_back(distance)
            return True, f"Moving backward {distance}cm"
        except Exception as e:
            return False, str(e)
    
    def move_left(self, distance=20):
        """Move left."""
        if not self.is_flying:
            return False, "Drone not flying"
        try:
            self.tello.move_left(distance)
            return True, f"Moving left {distance}cm"
        except Exception as e:
            return False, str(e)
    
    def move_right(self, distance=20):
        """Move right."""
        if not self.is_flying:
            return False, "Drone not flying"
        try:
            self.tello.move_right(distance)
            return True, f"Moving right {distance}cm"
        except Exception as e:
            return False, str(e)
    
    def move_up(self, distance=20):
        """Move up."""
        if not self.is_flying:
            return False, "Drone not flying"
        try:
            self.tello.move_up(distance)
            return True, f"Moving up {distance}cm"
        except Exception as e:
            return False, str(e)
    
    def move_down(self, distance=20):
        """Move down."""
        if not self.is_flying:
            return False, "Drone not flying"
        try:
            self.tello.move_down(distance)
            return True, f"Moving down {distance}cm"
        except Exception as e:
            return False, str(e)
    
    def rotate_clockwise(self, angle=45):
        """Rotate clockwise."""
        if not self.is_flying:
            return False, "Drone not flying"
        try:
            self.tello.rotate_clockwise(angle)
            return True, f"Rotating clockwise {angle}°"
        except Exception as e:
            return False, str(e)
    
    def rotate_counterclockwise(self, angle=45):
        """Rotate counter-clockwise."""
        if not self.is_flying:
            return False, "Drone not flying"
        try:
            self.tello.rotate_counter_clockwise(angle)
            return True, f"Rotating counter-clockwise {angle}°"
        except Exception as e:
            return False, str(e)
    
    def flip_forward(self):
        """Perform forward flip."""
        if not self.is_flying:
            return False, "Drone not flying"
        try:
            self.tello.flip_forward()
            return True, "Flipping forward"
        except Exception as e:
            return False, str(e)
    
    def flip_backward(self):
        """Perform backward flip."""
        if not self.is_flying:
            return False, "Drone not flying"
        try:
            self.tello.flip_back()
            return True, "Flipping backward"
        except Exception as e:
            return False, str(e)
    
    def flip_left(self):
        """Perform left flip."""
        if not self.is_flying:
            return False, "Drone not flying"
        try:
            self.tello.flip_left()
            return True, "Flipping left"
        except Exception as e:
            return False, str(e)
    
    def flip_right(self):
        """Perform right flip."""
        if not self.is_flying:
            return False, "Drone not flying"
        try:
            self.tello.flip_right()
            return True, "Flipping right"
        except Exception as e:
            return False, str(e)