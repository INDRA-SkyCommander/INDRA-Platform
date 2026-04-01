import tkinter as tk
from tkinter import ttk
import sys
import os
import json
import random

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

class ControllerGUI(tb.Window):
    def __init__(self):
        super().__init__(themename="darkly")
        
        self.title("INDRA - TELLO FLIGHT SYSTEMS")
        self.attributes('-fullscreen', True)
        self.bind("<Escape>", lambda e: self.destroy())

        # Path to the data file used by the reauth module
        self.data_path = os.path.join(os.path.dirname(__file__), '..', '..', "data", "module_input_data.json")

        # --- VIDEO FEED FOUNDATION ---
        self.video_canvas = tk.Canvas(self, bg="black", highlightthickness=0)
        self.video_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        
        self.video_label = tb.Label(self.video_canvas, text="[ NO VIDEO SIGNAL ]", 
                                   font=("Impact", 30), bootstyle="secondary")
        self.video_label.place(relx=0.5, rely=0.5, anchor="center")

        self._setup_hud()

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
        directions = ["f", "b", "l", "r"]
        print(f"UI_CMD: flip {random.choice(directions)}")

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

        tb.Label(top_bar, text="INDRA FLIGHT DECK", font=("Arial", 10, "bold")).pack(side="left", padx=20)
        
        self.stat_bat = tb.Label(top_bar, text="🔋 100%", font=("Courier", 14), bootstyle="success")
        self.stat_bat.pack(side="right", padx=20)

        # --- LEFT PANEL: FLIGHT OPERATIONS ---
        left_panel = tb.Frame(self, bootstyle="none")
        left_panel.place(relx=0.03, rely=0.5, anchor="w")

        tb.Button(left_panel, text="↑ TAKEOFF", width=15, bootstyle="success", 
                  command=lambda: print("UI_CMD: takeoff")).pack(pady=10)
        
        tb.Button(left_panel, text="↓ LAND", width=15, bootstyle="danger", 
                  command=lambda: print("UI_CMD: land")).pack(pady=10)
        
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

if __name__ == "__main__":
    # Ensure we run from the project root if testing manually
    app = ControllerGUI()
    app.mainloop()