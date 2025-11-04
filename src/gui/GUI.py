"""
README stuff
====================================================================
 INDRA GUI Main Module
--------------------------------------------------------------------
 File: GUI.py
 Description:
     This file defines the main graphical user interface for the
     INDRA software suite. The GUI provides functionality to:
         - Start, stop, and monitor live network scans
         - Display detected hosts and target information
         - Control modules and options
         - Run exploits through the exploitation framework
         - Display live visual data through the ImagePlayer widget
====================================================================
"""

# Standard Library
import os
import time
import threading
import subprocess
import shutil
import json

# Tkinter
import tkinter as tk
from tkinter import END, ACTIVE, StringVar, ttk

# Third-party
from PIL import Image, ImageTk
import sv_ttk

# Local Project Utils
from utils import sudo_exec, module_setup, scan, colors

# ===============================================================
# CLASS: MainGUI
# ===============================================================

class MainGUI:
    """
    The MainGUI class initializes and controls the main graphical user interface
    for the INDRA application. It contains GUI layout definitions, user interface
    event bindings, threading logic for background scans, and coordination with
    backend modules such as `scan`, `exploit`, and `indra_util`.
    """

    # ---------------------------------------------------------------
    # Class-Level Variables
    # ---------------------------------------------------------------
    module_options = []
    #host_list_update = True
    selected_host = None
    switch = False

    # Scan configuration
    interval = 1000
    packets = 10000
    scan_toggle = False
    is_scanning = False
    scanning_interface = ''
    auto_scanning_cooldown = 12  # seconds between auto-scans
    target_info = {}

    # Add module-required variables to the options list
    module_options.append(packets)

    # Threaded Scan helpers
    def run_scan_once(self):
        """
        Run a scan on the selected network interface in a new thread.
        Ensures that only one scan runs at a time.
        """
        self.is_scanning = True

        self.log("Beep boop. Scanning...")
        
        # Single scan
        def _scan_and_exit():
            try:
                # Implement and import scan
                self.target_info = scan(self.scanning_interface)
            finally:
                self.root.after(0, self.on_scan_complete)

        t = threading.Thread(target=_scan_and_exit)
        t.start()

    def auto_scan_loop(self):
        """
        Continuously runs scans in a loop with a cooldown period to avoid
        overwhelming the WiFi adapter. This function runs recursively in a thread.
        """
        while True:
            if self.scan_toggle and not self.is_scanning:
                self.run_scan_once()
            time.sleep(self.auto_scanning_cooldown)

    def get_scan_results(self):
            """
            This method is responsible for updating the list of all hosts shown in the GUI after scanning.
            """

            file_path = os.path.join(os.path.dirname(__file__), '..', '..', "data", "scan_results.txt")
            
            self.host_list_data_box.delete(0, END)
            try:
                with open(file_path, "r") as f:
                    for line in f:
                        if ("TELLO" in line):
                            self.host_list_data_box.insert(END, line)
            except FileNotFoundError:
                self.log(f"Scan results file not found at {file_path}.")
    
    def on_scan_complete(self):
        """
        Callback function to be executed when a scan is complete.
        Updates the GUI with the latest scan results.
        """
        self.get_scan_results()
        self.is_scanning = False

    def log(self, message: str):
        """
        Logs a message to the terminal output area in the GUI.
        """
        
        # Debug print to console
        print(message)
        
        self.root.after(0, self._log_update_gui, message)
        
    def _log_update_gui(self, message: str):
        """
        Updates the terminal output area in the GUI.
        """
        try:
            # Enable editing
            self.terminal_output_widget.config(state='normal')
            
            # Insert message
            self.terminal_output_widget.insert(END, message + "\n")
            
            # Auto-scroll down
            self.terminal_output_widget.see(END)
            
            self.terminal_output_widget.config(state='disabled')
        except Exception as e:
            self.log(f"Error updating terminal output: {e}")
        
    # GUI Initialization 
    def __init__(self, root: tk.Tk):
        """
        Initializes the INDRA Graphical User Interface (GUI).

        Args:
            root (tk.Tk): The main Tkinter root window object.
        """

        self.root = root
        root.title("INDRA")
        root.geometry("1200x675")
        root.resizable(False, False)
        root.update_idletasks()

        # Apply dark theme
        sv_ttk.set_theme("dark")

        # Variable Declaration
        self.current_target = StringVar()

        self.interval = MainGUI.interval
        self.packets = MainGUI.packets
        self.scan_toggle = False

        # Styling
        frame_style = ttk.Style()
        frame_style.configure("box.TFrame", background=colors.LIGHT_GREY)

        inner_frame_style = ttk.Style()
        inner_frame_style.configure("inner_box.TFrame", background=colors.SLATE)

        button_style = ttk.Style()
        button_style.configure("button.TButton", background=colors.SLATE, focuscolor=colors.SLATE)
        button_style.map("button.TButton", background=[("active", colors.SLATE)])

        exploit_button_style = ttk.Style()
        exploit_button_style.configure("exploit_button.TButton", foreground=colors.ORANGE)

        dropdown_style = ttk.Style()
        dropdown_style.configure("dropdown.TOptionsMenu", background=colors.SLATE)

        label_style = ttk.Style()
        label_style.configure("label.TLabel", background=colors.SLATE, foreground=colors.WHITE)

        # Start the background continuous-scan thread as a daemon
        self.toggle_scan_thread = threading.Thread(target=self.auto_scan_loop, daemon=True)
        self.toggle_scan_thread.start()

        # TOP BOX: Menu and Control Bar
        self.top_box = ttk.Frame(root, style="box.TFrame")
        self.top_box.pack(side="top", fill="x", expand=False, pady=5, padx=5, ipadx=5)

        menu_frame = ttk.Frame(self.top_box, style="box.TFrame")
        menu_frame.pack(side="top", pady=5)

        # Toggle scan button
        def toggle_scan():
            """
            Toggle automatic scanning and update button color.

            Value update is picked up by auto_scan_loop().
            """
            
            self.scan_toggle = not self.scan_toggle
            if self.scan_toggle:
                self.toggle_scan_button.config(bg=colors.ORANGE)
            else:
                self.toggle_scan_button.config(bg=colors.TKINTER_SLATE)

        self.toggle_scan_button = tk.Button(
            menu_frame,
            text="Toggle Scan",
            command=lambda: toggle_scan(),
            relief="flat",
            bg=colors.TKINTER_SLATE,
            justify="center",
            font=("Segoe UI", 10)
        )
        self.toggle_scan_button.pack(side="left", padx=5)

        # Scan button
        self.scan_button = ttk.Button(
            menu_frame,
            text="Scan",
            command=lambda: self.run_scan_once(),
            style="button.TButton"
        )
        self.scan_button.pack(side="left")

        # Interface selection dropdown
        def get_interfaces():
            """
            Return a list of available network interfaces.
            """
            output = subprocess.check_output('ifconfig | cut -d " " -f1', shell=True, text=True).strip()
            return [interface.replace(':', '') for interface in output.splitlines() if interface]

        def on_interface_selected(event=None):
            """
            Update scanning interface when user selects from dropdown.
            """
            MainGUI.scanning_interface = self.interface_dropdown.get()

        self.selected_interface = StringVar(root)
        self.selected_interface.set('interfaces')
        self.interface_dropdown = ttk.Combobox(
            menu_frame,
            values=get_interfaces(),
            state='readonly',
            textvariable=self.selected_interface
        )

        self.interface_dropdown.set('wlan0')
        self.interface_dropdown.bind("<<ComboboxSelected>>", on_interface_selected)
        self.interface_dropdown.pack(side="left", padx=5)

        # Modules Dropdown
        self.selected_module = StringVar(root)
        available_modules = module_setup()
        self.modules_dropdown = ttk.Combobox(
            menu_frame,
            textvariable=self.selected_module,
            values=available_modules,
            state='readonly'
        )
        self.modules_dropdown.set("Modules")
        self.modules_dropdown.pack(side="left", padx=5)

        # Options Dropdown
        def on_option_selected(event=None):
            """
            Executes actions based on selected option.
            """
            options_str = options_dropdown.get()
            self.option_info_label.grid(row=0, column=0, pady=5, padx=(25, 25), ipadx=60, sticky="n")

            match options_dropdown.get():
                case "Restart Network Adapter":
                    self.log('Restarting Network Adapter')
                    sudo_exec("service NetworkManager restart")
                case "Stop Monitor Mode":
                    self.log('Stopping Monitor Mode')
                    sudo_exec("airmon-ng stop wlan0")
                case _:
                    self.option_interval.grid_remove()
                    self.option_info_label.grid_remove()

            self.option_info_label.config(text=f"Option: {options_str}")

        self.selected_option = StringVar(root)
        self.selected_option.set("")
        options_dropdown = ttk.Combobox(
            menu_frame,
            textvariable=self.selected_option,
            values=["Interval", "Packets", "Restart Network Adapter", "Stop Monitor Mode"],
            state='readonly'
        )
        options_dropdown.set("Options")
        options_dropdown.bind("<<ComboboxSelected>>", on_option_selected)
        options_dropdown.pack(side="left", padx=5)

        # Exploit Button

        def get_target_info(target_name):
            """
            Retrieves target information from scan results
            """

            #TODO: There is still an unresolved issue with get_target_info returning less than 6 elements
            
            info_dict = self.target_info

            if target_name.strip() in info_dict:
                return info_dict[target_name.strip()]
            else:
                return ['','','','','','']
            
        def update_target():
            """
            Updates information based on the selected target

            Args:
                list_box: listbox containing target items
                target_label: label to display target name
                target_info_label: label to display target info
            """

            self.current_target = self.host_list_data_box.get(ACTIVE)
            self.log(self.current_target)
            target_info_list = get_target_info(self.current_target) # Had to remove every .get() because it was throwing error

            self.target_label.configure(text=f"Target: {self.current_target}")
            self.target_label.update()

            self.target_info_label.configure(text=f"MAC: {target_info_list[1]}\n"\
                                                  f"Quality: {target_info_list[2]}\n"\
                                                  f"Channel: {target_info_list[3]}\n"\
                                                  f"Signal Level: {target_info_list[4]}\n"\
                                                  f"Encryption: {target_info_list[5]}")
            self.target_info_label.update()

            return

        def run_exploit(gui_selected_module, target_name, target_info, options_info) -> int:
            """
            Will write current state of software and selected target to module_input_data.json

            After writing, will run the selected module with the parameters set in module_input_data.json
            """
            
            module_input_file_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "module_input_data.json")

            # Writing to JSON
            output_data = {
                "target_name": target_name.strip(),
                "target_info": {
                    "raw_string": target_info[0].strip() if len(target_info) > 0 else "",
                    "mac_address": target_info[1].strip() if len(target_info) > 1 else "",
                    "quality": target_info[2].strip() if len(target_info) > 2 else "",
                    "channel": target_info[3].strip() if len(target_info) > 3 else "",
                    "signal_level": target_info[4].strip() if len(target_info) > 4 else "",
                    "encryption": target_info[5].strip() if len(target_info) > 5 else ""
                },
                # No clue what writing 10000 to the file does, but it's in the original code
                "options": {
                    "packets": options_info[0] if len(options_info) > 0 else 10000
                }                
            }
            
            try:
                with open(module_input_file_path, "w") as json_file:
                    json.dump(output_data, json_file, indent=4)
            except Exception as e:
                self.log(f"Error writing to JSON file: {e}")
                return -1
            
            module_file_path = os.path.join(os.path.dirname(__file__), "..", "..", "modules", f"{gui_selected_module}", f"{gui_selected_module}.py")
            
            print(f"Launching module: {gui_selected_module} on target: {target_name}")
            
            try:
                module_return_code = subprocess.call(['/usr/bin/python3.11', module_file_path])
                print(f"Module {gui_selected_module} finished with return code {module_return_code}")
                return module_return_code
            except Exception as e:
                print(f"Error running module {gui_selected_module}: {e}")
                return -1

        def run_exploit_thread():
            """
            Runs the selected exploit module in a background thread.
            """
            module_name = self.selected_module.get()
            
            if self.is_scanning:
                self.log("Stop scanning before launching a module!")
                return
            
            if module_name == "Modules":
                self.log("Please select a module before hitting \"exploit\"!")
                return
            
            self.log(f"Running module: {module_name}")
            
            update_target()
            current_target = self.current_target
            target_info_list = get_target_info(current_target)
            options_info_list = self.module_options
            
            # Implement and import exploit
            exploit_thread = threading.Thread(target=run_exploit, args=(module_name, current_target, target_info_list, options_info_list), daemon=True)
            exploit_thread.start()

        exploit_button = tk.Button(
            menu_frame,
            text="EXPLOIT",
            command=lambda: run_exploit_thread(),
            bg=colors.ORANGE,
            relief="flat",
            activebackground=colors.ORANGE,
            highlightcolor=colors.LIGHT_ORANGE,
            justify="center",
            font=("Segoe UI", 30)
        )
        exploit_button.pack(side="left", padx=5)
 
        # LEFT BOX: Host List
        self.side_box = ttk.Frame(root, padding=(5, 5, 10, 10), style="box.TFrame")
        self.side_box.pack(side="left", fill="y", expand=False, padx=5, pady=5)

        host_list_label = ttk.Label(self.side_box, text="Host List", style="label.TLabel")
        host_list_label.configure(anchor="center",
                                  font=("default", 16, "bold"),
                                  foreground=colors.WHITE)
        host_list_label.grid(row=0, column=0, pady=5, padx=(30, 30), ipadx=50, sticky="n")

        self.inner_side_box = ttk.Frame(self.side_box, padding=(5, 5, 10, 10), style="inner_box.TFrame")
        self.inner_side_box.grid(row=1, column=0, pady=5, padx=(30, 30), sticky="n")

        # Listbox displaying discovered hosts

        self.host_list_data_box = tk.Listbox(
            self.inner_side_box,
            width=30,
            height=30,
            justify="left",
            font=("Segoe UI", 10),
            highlightcolor=colors.LIGHT_ORANGE,
            fg=colors.WHITE,
            selectbackground=colors.LIGHT_ORANGE,
            selectforeground=colors.WHITE,
            highlightthickness=0,
            borderwidth=0,
            selectmode="single",
            relief="flat"
        )
        self.host_list_data_box.grid(row=0, column=0, pady=5, padx=(30, 30), ipadx=30, sticky="n")

        # CENTER BOX: Target Information and Options
        self.center_box = ttk.Frame(root, style="box.TFrame")
        self.center_box.pack(side="top", fill="x", expand=False, pady=5, padx=5, ipadx=5)

        center_frame = ttk.Frame(self.center_box, style="box.TFrame")
        center_frame.pack(side="top", pady=5)

        info_label = ttk.Label(center_frame, text="Information")
        info_label.configure(anchor="center",
                             font=("default", 16, "bold"),
                             foreground=colors.WHITE)
        info_label.grid(row=0, column=0, pady=5, padx=(250, 250), ipadx=80, sticky="n")

        self.target_label = ttk.Label(center_frame, text=f"Target: {self.current_target.get()}")
        self.target_label.configure(anchor="center",
                                    font=("default", 12),
                                    foreground=colors.WHITE)
        self.target_label.grid(row=1, column=0, pady=5, padx=(30, 30), ipadx=50, sticky="nw")

        self.target_info_label = ttk.Label(
            center_frame,
            text="Quality: \nChannel: \nSignal Level: \nEncryption: "
        )
        self.target_info_label.configure(anchor="center",
                                         font=("default", 12),
                                         foreground=colors.WHITE)
        self.target_info_label.grid(row=2, column=0, pady=5, padx=(30, 30), ipadx=50, sticky="nw")

        # Bottom Section of Center Box (Options)
        center_frame_bottom = ttk.Frame(self.center_box, style="box.TFrame")
        center_frame_bottom.pack(side="bottom", pady=5)

        self.option_info_label = ttk.Label(center_frame_bottom, text="Options")
        self.option_info_label.configure(anchor="center",
                                    font=("default", 16, "bold"),
                                    foreground=colors.WHITE)

        self.option_interval = tk.Scale(
            center_frame_bottom,
            from_=1000,
            to=100000,
            orient="horizontal",
            length=400
        )

        # TERMINAL BOX: Output Log
        self.bottom_box = ttk.Frame(root, style="box.TFrame")
        self.bottom_box.pack(side="bottom", fill="x", expand=False, pady=5, padx=5, ipadx=5)
        self.bottom_box.grid_columnconfigure(0, weight=1)
        self.bottom_box.grid_rowconfigure(1, weight=1)

        terminal_title = ttk.Label(self.bottom_box, text="Terminal Output")
        terminal_title.configure(anchor="center")
        terminal_title.grid(row=0, column=0, pady=5, padx=(30, 30), ipadx=50, sticky="n")

        # Frame for text widget and scrollbar
        log_frame = ttk.Frame(self.bottom_box)
        log_frame.grid(row=1, column=0, pady=(10, 20), padx=(30, 30), sticky="nsew")
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)
        
        # Scrollbar
        self.terminal_scrollbar = ttk.Scrollbar(log_frame, orient="vertical")
        self.terminal_scrollbar.grid(row=0, column=1, sticky="ns")
        
        self.terminal_output_widget = tk.Text(
            log_frame,
            width=20,
            height=10,
            font=("Segoe UI", 10),
            fg=colors.WHITE,
            bg=colors.SLATE,
            highlightthickness=0,
            borderwidth=0,
            relief="flat",
            selectbackground=colors.LIGHT_ORANGE,
            yscrollcommand=self.terminal_scrollbar.set,
            state='disabled'
        )
        self.terminal_output_widget.grid(row=0, column=0, sticky="nsew")
        self.terminal_scrollbar.config(command=self.terminal_output_widget.yview)

        # RIGHT BOX: Image Player (Video Feed)
        image_folder = os.path.join(os.path.dirname(__file__), "..", "data", "images")
        os.makedirs(image_folder, exist_ok=True)
        self.image_player = ImagePlayer(root, image_folder=image_folder, frame_rate=2)

        self.image_player.stop()
        self.image_player.pack(side="right", fill="both", expand=True, padx=5, pady=5)

# CLASS: ImagePlayer
class ImagePlayer(ttk.Frame):
    """
    The ImagePlayer class is a widget designed to display images
    sequentially from a specified folder, acting as a lightweight
    video player.
    """

    def __init__(self, parent, image_folder, frame_rate=2):
        super().__init__(parent)
        self.frame_rate = frame_rate
        self.image_folder = image_folder
        self.images = []       # List of all images in the folder
        self.new_images = []   # List of newly added images
        self.current_image_index = 0
        self.paused = True

        self.label = ttk.Label(self)
        self.label.pack(expand=True, fill="both")

        os.makedirs(self.image_folder, exist_ok=True)
        
        self._clear_folder()

        self.load_images()
        self.monitor_folder()

    def _clear_folder(self):
        """Clears the contents of the image folder."""
        
        self.images = []
        self.new_images = []
        self.current_image_index = 0
        
        if os.path.exists(self.image_folder):
            for filename in os.listdir(self.image_folder):
                file_path = os.path.join(self.image_folder, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f"Failed to clear {file_path}. Reason: {e}")

    def load_images(self):
        """Loads all images from the folder and identifies new images."""
        all_images = [
            os.path.join(self.image_folder, f)
            for f in sorted(os.listdir(self.image_folder))
            if f.lower().endswith(('.png', '.jpg', '.jpeg'))
        ]
        new_images = [img for img in all_images if img not in self.images]
        self.images.extend(new_images)
        self.new_images.extend(new_images)

    def monitor_folder(self):
        """
        Continuously monitors the folder for newly added images.
        Automatically starts playback if new images are found.
        """
        self.load_images()
        if self.new_images and self.paused:
            self.start()
        self.after(1000, self.monitor_folder)

    def play_images(self):
        """Displays newly added images at the specified frame rate."""
        if not self.paused and self.new_images:
            img_path = self.new_images.pop(0)
            try:
                img = Image.open(img_path)
                img = img.resize((730, 300))
                tk_img = ImageTk.PhotoImage(img)
                self.label.config(image=tk_img)
                self.label.image = tk_img # Reference to avoid garbage collection
                self.after(int(1000 / self.frame_rate), self.play_images)
            except Exception as e:
                print(f"Error displaying {img_path}: {e}")

    def start(self):
        """
        Starts playback.
        """
        if self.paused:
            self.paused = False
            self.play_images()
    
    def stop(self):
        """
        Stops playback.
        """
        self.paused = True
    
    def toggle_playback(self):
        """
        Toggle between start and stop.
        """
        if self.paused:
            self.start()
        else:
            self.stop()

