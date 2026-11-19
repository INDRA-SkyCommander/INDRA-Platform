import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
import json
import random
import threading

try:
    import pygame
except ImportError:
    pygame = None

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

        # --- PS4 CONTROLLER INPUT ---
        self.ps4 = None
        self.ps4_deadzone = 0.35
        self.ps4_poll_ms = 40   # ~25 Hz; visualization only for now

        # Confirmed Linux/Pygame mapping from this controller:
        # Axis 0 = left stick X, Axis 1 = left stick Y
        # Axis 2 = L2, Axis 3 = right stick X
        # Axis 4 = right stick Y, Axis 5 = R2
        # Hat 0 = D-pad
        self.ps4_axes = {
            "left_x": 0,
            "left_y": 1,
            "l2": 2,
            "right_x": 3,
            "right_y": 4,
            "r2": 5,
        }

        # Confirmed DualShock 4 button mapping from this VM/controller.
        self.ps4_buttons = {
            "cross": 0,
            "circle": 1,
            "triangle": 2,
            "square": 3,
            "l1": 4,
            "r1": 5,
            "share": 8,
            "options": 9,
            "ps": 10,
            "left_stick": 11,
            "right_stick": 12,
        }

        # Used for rising-edge detection so a held button fires only once.
        self.ps4_button_prev = {
            name: False for name in self.ps4_buttons
        }

        # --- VIDEO FEED FOUNDATION ---
        self.video_canvas = tk.Canvas(self, bg="black", highlightthickness=0)
        self.video_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        
        self.video_label = tb.Label(self.video_canvas, text="[ NO VIDEO SIGNAL ]", 
                                   font=("Impact", 30), bootstyle="secondary")
        self.video_label.place(relx=0.5, rely=0.5, anchor="center")

        self._setup_hud()
        self._bind_keys()
        self._init_ps4_controller()
        self.after(self.ps4_poll_ms, self._poll_ps4_controller)

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


        # --- BOTTOM-RIGHT: TRANSPARENT PS4 INPUT HUD ---
        # Drawn directly onto video_canvas so a future camera image remains
        # visible behind the controls. Inactive buttons have no fill.
        self.ps4_indicators = {}

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()

        # HUD sizing / spacing.
        box_w = 82
        box_h = 34
        gap = 8
        diamond_w = 3 * box_w + 2 * gap
        right_margin = 28
        bottom_margin = 34
        diamond_gap = 36

        # Position the two diamonds together in the lower-right corner.
        total_w = diamond_w * 2 + diamond_gap
        hud_x = screen_w - right_margin - total_w
        hud_y = screen_h - bottom_margin - (3 * box_h + 2 * gap)

        self.ps4_hud_style = {
            "inactive_outline": "#6f858c",
            "inactive_text": "#92a3a8",
            "active_fill": "#1d7a4c",
            "active_outline": "#39e58c",
            "active_text": "#ffffff",
            "status": "#31e6b2",
            "value_text": "#73868b",
        }

        # Status line above both diamonds.
        self.ps4_status = self.video_canvas.create_text(
            hud_x,
            hud_y - 30,
            text="PS4: NOT DETECTED",
            anchor="w",
            fill=self.ps4_hud_style["status"],
            font=("Courier", 10, "bold")
        )

        def make_indicator(name, label, x, y):
            rect = self.video_canvas.create_rectangle(
                x, y, x + box_w, y + box_h,
                outline=self.ps4_hud_style["inactive_outline"],
                width=1,
                fill=""
            )
            txt = self.video_canvas.create_text(
                x + box_w / 2,
                y + box_h / 2,
                text=label,
                fill=self.ps4_hud_style["inactive_text"],
                font=("Arial", 9, "bold")
            )
            self.ps4_indicators[name] = (rect, txt)

        # LEFT DIAMOND: planar movement
        move_x = hud_x

        make_indicator(
            "forward", "↑ FWD",
            move_x + box_w + gap,
            hud_y
        )
        make_indicator(
            "left", "← LEFT",
            move_x,
            hud_y + box_h + gap
        )
        make_indicator(
            "right", "RIGHT →",
            move_x + 2 * (box_w + gap),
            hud_y + box_h + gap
        )
        make_indicator(
            "backward", "↓ BACK",
            move_x + box_w + gap,
            hud_y + 2 * (box_h + gap)
        )

        # RIGHT DIAMOND: yaw + altitude
        orient_x = move_x + diamond_w + diamond_gap

        make_indicator(
            "up", "⇧ UP",
            orient_x + box_w + gap,
            hud_y
        )
        make_indicator(
            "yaw_ccw", "↶ YAW",
            orient_x,
            hud_y + box_h + gap
        )
        make_indicator(
            "yaw_cw", "YAW ↷",
            orient_x + 2 * (box_w + gap),
            hud_y + box_h + gap
        )
        make_indicator(
            "down", "⇩ DOWN",
            orient_x + box_w + gap,
            hud_y + 2 * (box_h + gap)
        )

        self.ps4_values = self.video_canvas.create_text(
            screen_w - right_margin,
            hud_y + 3 * (box_h + gap) + 4,
            text="LS(0.00, 0.00)   RS(0.00, 0.00)   D-PAD(0, 0)",
            anchor="e",
            fill=self.ps4_hud_style["value_text"],
            font=("Courier", 9)
        )

    def _init_ps4_controller(self):
        """Initialize the first joystick visible to pygame."""
        if pygame is None:
            self.video_canvas.itemconfigure(
                self.ps4_status,
                text="PS4: PYGAME NOT INSTALLED",
                fill="#ff6666"
            )
            print("[!] pygame not installed. Run: python3 -m pip install pygame")
            return

        try:
            pygame.display.init()
            pygame.joystick.init()

            count = pygame.joystick.get_count()
            if count < 1:
                self.video_canvas.itemconfigure(
                    self.ps4_status,
                    text="PS4: NOT DETECTED",
                    fill="#ff6666"
                )
                print("[!] No controller detected by pygame.")
                return

            self.ps4 = pygame.joystick.Joystick(0)
            self.ps4.init()

            name = self.ps4.get_name()
            self.video_canvas.itemconfigure(
                self.ps4_status,
                text=f"PS4: {name}",
                fill=self.ps4_hud_style["status"]
            )
            print(f"[+] Controller detected: {name}")
            print(
                f"    Axes={self.ps4.get_numaxes()} "
                f"Buttons={self.ps4.get_numbuttons()} "
                f"Hats={self.ps4.get_numhats()}"
            )

        except Exception as e:
            self.ps4 = None
            self.video_canvas.itemconfigure(
                self.ps4_status,
                text="PS4: INPUT ERROR",
                fill="#ff6666"
            )
            print(f"[!] PS4 initialization failed: {e}")

    def _set_ps4_indicator(self, name, active):
        """Change an on-screen PS4 direction indicator."""
        items = self.ps4_indicators.get(name)
        if items is None:
            return

        rect, txt = items

        if active:
            self.video_canvas.itemconfigure(
                rect,
                fill=self.ps4_hud_style["active_fill"],
                outline=self.ps4_hud_style["active_outline"],
                width=2
            )
            self.video_canvas.itemconfigure(
                txt,
                fill=self.ps4_hud_style["active_text"]
            )
        else:
            self.video_canvas.itemconfigure(
                rect,
                fill="",
                outline=self.ps4_hud_style["inactive_outline"],
                width=1
            )
            self.video_canvas.itemconfigure(
                txt,
                fill=self.ps4_hud_style["inactive_text"]
            )

    def _handle_ps4_button_press(self, name):
        """
        Handle one-shot DualShock 4 button presses.

        Movement remains separate from these actions. This method is only
        called on the transition from released -> pressed.
        """
        print(f"[PS4] {name.upper()} pressed")

        if name == "options":
            self._connect()

        elif name == "cross":
            self._takeoff()

        elif name == "circle":
            self._land()

        elif name == "triangle":
            self.random_flip()

        elif name == "square":
            # Reserved for future screenshot implementation.
            print("UI_CMD: screenshot")

        # Intentionally unassigned for now:
        # L1, R1, Share, PS, L3, R3.
        # We can map these later once their desired behavior is decided.

    def _poll_ps4_controller(self):
        """
        Read the mapped DualShock 4 controls and update the GUI.

        Stick movement is still visualization-only at this stage.
        Mapped face/options buttons may trigger their one-shot GUI actions.
        """
        if pygame is None:
            return

        try:
            pygame.event.pump()

            # Hot-plug support: try to acquire a joystick if one appears later.
            if self.ps4 is None:
                if pygame.joystick.get_count() > 0:
                    self._init_ps4_controller()
                self.after(self.ps4_poll_ms, self._poll_ps4_controller)
                return

            lx = self.ps4.get_axis(self.ps4_axes["left_x"])
            ly = self.ps4.get_axis(self.ps4_axes["left_y"])
            rx = self.ps4.get_axis(self.ps4_axes["right_x"])
            ry = self.ps4.get_axis(self.ps4_axes["right_y"])

            if self.ps4.get_numhats() > 0:
                hat_x, hat_y = self.ps4.get_hat(0)
            else:
                hat_x, hat_y = (0, 0)

            # Read all mapped buttons and fire actions only on rising edges.
            for name, button_index in self.ps4_buttons.items():
                pressed = bool(self.ps4.get_button(button_index))
                was_pressed = self.ps4_button_prev.get(name, False)

                if pressed and not was_pressed:
                    self._handle_ps4_button_press(name)

                self.ps4_button_prev[name] = pressed

            dz = self.ps4_deadzone

            # Left stick = planar movement visualization.
            # Axis 1: negative is up/forward, positive is down/backward.
            forward = ly < -dz
            backward = ly > dz
            left = lx < -dz
            right = lx > dz

            # Right stick = yaw and vertical movement visualization.
            # Axis 3: negative left, positive right.
            # Axis 4: negative up, positive down.
            yaw_ccw = rx < -dz
            yaw_cw = rx > dz
            up = ry < -dz
            down = ry > dz

            # Also allow the D-pad to illuminate the planar indicators.
            forward = forward or (hat_y == 1)
            backward = backward or (hat_y == -1)
            left = left or (hat_x == -1)
            right = right or (hat_x == 1)

            self._set_ps4_indicator("forward", forward)
            self._set_ps4_indicator("backward", backward)
            self._set_ps4_indicator("left", left)
            self._set_ps4_indicator("right", right)
            self._set_ps4_indicator("yaw_ccw", yaw_ccw)
            self._set_ps4_indicator("yaw_cw", yaw_cw)
            self._set_ps4_indicator("up", up)
            self._set_ps4_indicator("down", down)

            self.video_canvas.itemconfigure(
                self.ps4_values,
                text=(
                    f"LS({lx:+.2f}, {ly:+.2f})   "
                    f"RS({rx:+.2f}, {ry:+.2f})   "
                    f"D-PAD({hat_x:+d}, {hat_y:+d})"
                )
            )

        except pygame.error as e:
            print(f"[!] Controller disconnected: {e}")
            self.ps4 = None
            self.video_canvas.itemconfigure(
                self.ps4_status,
                text="PS4: DISCONNECTED",
                fill="#ff6666"
            )

        except Exception as e:
            print(f"[!] PS4 polling error: {e}")

        self.after(self.ps4_poll_ms, self._poll_ps4_controller)

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