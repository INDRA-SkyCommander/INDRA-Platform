import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
import json
import random
import threading

# Import your custom utility for the disconnect command
# Note: Ensure your PYTHONPATH is set correctly so it finds src.utils
try:
    from src.utils import sudo_exec
except ImportError:
    # Fallback for manual testing if src.utils isn't in path
    def sudo_exec(cmd): print(f"[MOCK SUDO]: {cmd}")

try:
    import ttkbootstrap as tb
    from ttkbootstrap.constants import *
except ImportError:
    print("[!] Error: ttkbootstrap not found. Run: /usr/bin/python3.11 -m pip install ttkbootstrap")
    sys.exit(1)

try:
    from djitellopy import Tello
except ImportError:
    print("[!] Error: djitellopy not found. Run: /usr/bin/python3.11 -m pip install djitellopy")
    sys.exit(1)


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
        self.connect_lock = threading.Lock()
        
    def connect(self):
        """Establish connection to the drone."""
        with self.connect_lock:
            if self.is_connected and self.tello is not None:
                return True, "Already connected to drone"

            try:
                if self.tello is not None:
                    try:
                        self.tello.end()
                    except Exception:
                        pass
                    self.tello = None

                self.tello = Tello()
                self.tello.connect()
                battery = self.tello.get_battery()
                self.is_connected = True
                return True, f"Connected! Battery: {battery}%"
            except Exception as e:
                error_msg = str(e)
                self.is_connected = False

                if "Address already in use" in error_msg or "Errno 98" in error_msg:
                    try:
                        if self.tello:
                            self.tello.end()
                    except Exception:
                        pass
                    self.tello = None
                    return False, "Connection failed: UDP port already in use ([Errno 98]). Close other Tello sessions and retry."

                self.tello = None
                return False, f"Connection failed: {error_msg}"
    
    def disconnect(self):
        """Safely disconnect from the drone."""
        with self.connect_lock:
            try:
                if self.is_flying:
                    self.land()
                if self.tello:
                    self.tello.end()
                self.is_connected = False
                self.is_flying = False
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

class ControllerGUI(tb.Window):
    def __init__(self):
        super().__init__(themename="darkly")
        
        self.title("INDRA - TELLO FLIGHT SYSTEMS")
        self.attributes('-fullscreen', True)
        self.bind("<Escape>", lambda e: self.destroy())

        # Path to the data file used by the reauth module
        self.data_path = os.path.join(os.path.dirname(__file__), '..', '..', "data", "module_input_data.json")

        # Initialize drone controller
        self.controller = TelloController()
        self.movement_distance = 20  # cm
        self.is_connecting = False

        # --- VIDEO FEED FOUNDATION ---
        self.video_canvas = tk.Canvas(self, bg="black", highlightthickness=0)
        self.video_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        
        self.video_label = tb.Label(self.video_canvas, text="[ NO VIDEO SIGNAL ]", 
                                   font=("Impact", 30), bootstyle="secondary")
        self.video_label.place(relx=0.5, rely=0.5, anchor="center")

        self._setup_hud()
        self._bind_keys()
        
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def disconnect_drone(self):
        """
        Logic: The opposite of Reauth.
        Reads the interface from JSON and severs the link.
        """
        interface = "wlan0" # Default fallback
        
        try:
            if os.path.exists(self.data_path):
                with open(self.data_path, 'r') as file:
                    scan_info = json.load(file)
                    options_info = scan_info.get("options", {})
                    interface = options_info.get("interface", "wlan0")
            
            print(f"[*] Forcefully disconnecting interface: {interface}...")
            # The 'nmcli device disconnect' command severs the link
            sudo_exec(f"nmcli device disconnect {interface}")
            print("[+] Connection Severed.")
            
        except Exception as e:
            print(f"[!] Disconnect failed: {e}")
        
        # Close the flight deck after sending the command
        self.destroy()

    def random_flip(self):
        """Random flip for fun"""
        directions = ["forward", "backward", "left", "right"]
        self._flip(random.choice(directions))

    def _setup_hud(self):
        # --- TOP TELEMETRY BAR ---
        top_bar = tb.Frame(self, bootstyle="dark", height=60)
        top_bar.place(relx=0, rely=0, relwidth=1)

        # EXIT BUTTON (Standard tk.Button for VM stability)
        exit_btn = tk.Button(top_bar, text="✖ EXIT", command=self.destroy, 
                            bg="#222222", fg="#ee5555", font=("Arial", 9, "bold"),
                            relief="flat", padx=10, pady=5)
        exit_btn.pack(side="left", padx=(15, 5), pady=10)

        # DISCONNECT BUTTON (Standard tk.Button for VM stability)
        disc_btn = tk.Button(top_bar, text="⎋ DISCONNECT", command=self.disconnect_drone, 
                            bg="#333333", fg="#ffffff", font=("Arial", 9, "bold"),
                            relief="flat", padx=10, pady=5)
        disc_btn.pack(side="left", padx=5, pady=10)

        self.connect_btn = tk.Button(top_bar, text="⦿ CONNECT", command=self._connect,
                    bg="#234f23", fg="#ffffff", font=("Arial", 9, "bold"),
                    relief="flat", padx=10, pady=5)
        self.connect_btn.pack(side="left", padx=5, pady=10)

        tb.Label(top_bar, text="INDRA FLIGHT DECK", font=("Arial", 10, "bold")).pack(side="left", padx=20)

        self.stat_conn = tb.Label(top_bar, text="● OFFLINE", font=("Courier", 12), bootstyle="danger")
        self.stat_conn.pack(side="right", padx=(5, 20))
        
        self.stat_bat = tb.Label(top_bar, text="🔋 --%", font=("Courier", 14), bootstyle="secondary")
        self.stat_bat.pack(side="right", padx=20)

        # --- LEFT PANEL: FLIGHT OPERATIONS ---
        left_panel = tb.Frame(self, bootstyle="none")
        left_panel.place(relx=0.03, rely=0.5, anchor="w")

        tb.Button(left_panel, text="↑ TAKEOFF", width=15, bootstyle="success", 
                  command=self._takeoff).pack(pady=10)
        
        tb.Button(left_panel, text="↓ LAND", width=15, bootstyle="danger", 
                  command=self._land).pack(pady=10)
        
        tb.Button(left_panel, text="✨ FLIP", width=15, bootstyle="info-outline", 
                  command=self.random_flip).pack(pady=20)

        # --- RIGHT PANEL: MEDIA CONTROLS ---
        right_panel = tb.Frame(self, bootstyle="none")
        right_panel.place(relx=0.97, rely=0.5, anchor="e")

        tb.Label(right_panel, text="MEDIA", font=("Arial", 10, "bold")).pack(pady=10)
        
        tb.Button(right_panel, text="📸 SCREENSHOT", width=15, bootstyle="light",
                  command=lambda: print("UI_CMD: screenshot")).pack(pady=5)
        
        tb.Button(right_panel, text="🔴 RECORD", width=15, bootstyle="danger-outline",
                  command=lambda: print("UI_CMD: toggle_record")).pack(pady=5)

    def _bind_keys(self):
        """Bind keyboard events for drone control."""
        # WASD for directional movement
        self.bind("<w>", lambda e: self._move("forward"))
        self.bind("<W>", lambda e: self._move("forward"))
        self.bind("<a>", lambda e: self._move("left"))
        self.bind("<A>", lambda e: self._move("left"))
        self.bind("<s>", lambda e: self._move("backward"))
        self.bind("<S>", lambda e: self._move("backward"))
        self.bind("<d>", lambda e: self._move("right"))
        self.bind("<D>", lambda e: self._move("right"))
        
        # Arrow keys for up/down movement
        self.bind("<Up>", lambda e: self._move("up"))
        self.bind("<Down>", lambda e: self._move("down"))
        
        # Left/Right arrow keys for rotation
        self.bind("<Left>", lambda e: self._rotate("ccw"))
        self.bind("<Right>", lambda e: self._rotate("cw"))
        
        self.bind("<space>", lambda e: self._takeoff())
        self.bind("<BackSpace>", lambda e: self._land())
    
    def _connect(self):
        """Connect to drone in a background thread."""
        if self.is_connecting:
            return

        if self.controller.is_connected:
            print("Already connected to drone")
            return

        self.is_connecting = True
        self.connect_btn.configure(state=tk.DISABLED, text="… CONNECTING")

        def connect_thread():
            success, msg = self.controller.connect()
            self.after(0, lambda: self._on_connect_complete(success, msg))
        
        threading.Thread(target=connect_thread, daemon=True).start()
    
    def _on_connect_complete(self, success, msg):
        """Handle connection completion."""
        self.is_connecting = False
        self.connect_btn.configure(state=tk.NORMAL, text="⦿ CONNECT")
        print(msg)

        if success:
            battery = self.controller.get_battery()
            self.stat_conn.configure(text="● ONLINE", bootstyle="success")
            if battery is not None:
                self.stat_bat.configure(text=f"🔋 {battery}%", bootstyle="success")
            return

        self.stat_conn.configure(text="● OFFLINE", bootstyle="danger")
        self.stat_bat.configure(text="🔋 --%", bootstyle="secondary")
        if "Not connected to drone" not in msg:
            messagebox.showerror("Connection Error", msg)
    
    def _takeoff(self):
        """Takeoff command."""
        if not self.controller.is_connected:
            print("Not connected to drone. Press CONNECT first.")
            return

        def takeoff_thread():
            success, msg = self.controller.takeoff()
            self.after(0, lambda: self._on_takeoff_complete(success, msg))
        
        threading.Thread(target=takeoff_thread, daemon=True).start()
    
    def _on_takeoff_complete(self, success, msg):
        """Handle takeoff completion."""
        print(msg)
        if not success and "Not connected to drone" not in msg:
            messagebox.showerror("Takeoff Error", msg)
    
    def _land(self):
        """Land command."""
        def land_thread():
            success, msg = self.controller.land()
            self.after(0, lambda: self._on_land_complete(success, msg))
        
        threading.Thread(target=land_thread, daemon=True).start()
    
    def _on_land_complete(self, success, msg):
        """Handle landing completion."""
        print(msg)
    
    def _move(self, direction):
        """Handle movement commands."""
        if not self.controller.is_connected or not self.controller.is_flying:
            return
        
        def move_thread():
            distance = self.movement_distance
            if direction == "forward":
                success, msg = self.controller.move_forward(distance)
            elif direction == "backward":
                success, msg = self.controller.move_backward(distance)
            elif direction == "left":
                success, msg = self.controller.move_left(distance)
            elif direction == "right":
                success, msg = self.controller.move_right(distance)
            elif direction == "up":
                success, msg = self.controller.move_up(distance)
            elif direction == "down":
                success, msg = self.controller.move_down(distance)
            
            self.after(0, lambda: print(msg))
        
        threading.Thread(target=move_thread, daemon=True).start()
    
    def _rotate(self, direction):
        """Handle rotation commands."""
        if not self.controller.is_connected or not self.controller.is_flying:
            return
        
        def rotate_thread():
            if direction == "cw":
                success, msg = self.controller.rotate_clockwise(45)
            else:
                success, msg = self.controller.rotate_counterclockwise(45)
            
            self.after(0, lambda: print(msg))
        
        threading.Thread(target=rotate_thread, daemon=True).start()
    
    def _flip(self, direction):
        """Handle flip commands."""
        if not self.controller.is_connected or not self.controller.is_flying:
            return
        
        def flip_thread():
            if direction == "forward":
                success, msg = self.controller.flip_forward()
            elif direction == "backward":
                success, msg = self.controller.flip_backward()
            elif direction == "left":
                success, msg = self.controller.flip_left()
            elif direction == "right":
                success, msg = self.controller.flip_right()
            
            self.after(0, lambda: print(msg))
        
        threading.Thread(target=flip_thread, daemon=True).start()
    
    def _on_closing(self):
        """Handle window closing."""
        if self.controller.is_connected:
            self.controller.disconnect()
        self.destroy()

if __name__ == "__main__":
    # Ensure we run from the project root if testing manually
    app = ControllerGUI()
    app.mainloop()