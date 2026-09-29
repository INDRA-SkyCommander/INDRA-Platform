# Standard Libraries
import os
import sys
import json
import time
import queue
import base64
import threading
import subprocess
import re
from datetime import datetime, timezone

# Tkinter
import tkinter as tk
from tkinter import font
import ttkbootstrap as tb
from ttkbootstrap.constants import *  # pyright: ignore[reportWildcardImportFromLibrary]


# Custom Modules
from src.utils import sudo_exec, module_setup
from src.utils.scan import scan, SCAN_ERROR_UNSUPPORTED_INTERFACE, SCAN_ERROR_GENERIC

class IndraGUI(tb.Window):
    """
    The IndraGUI class initializes and controls the main graphical user interface
    for the INDRA application. It contains GUI layout definitions, user interface
    event bindings, threading logic for background scans, and coordination with
    backend modules.
    """

    def __init__(self):
        super().__init__(themename="darkly")

        #Connection Watcher
        self.drone_connected = False
        self.controller_process = None
        self.conn_thread = threading.Thread(target=self.connection_watcher, daemon=True)
        self.conn_thread.start()

        # Tkinter Window
        self.title("INDRA")
        self.geometry("1400x850")
        self.resizable(True, True)

        # Data Stuctures
        self.all_targets = {}
        self.video_playing = False

        # Scan variables
        self.scan_toggled = False
        self.is_scanning = False
        self.auto_scan_cooldown = 10
        
        # Top bar variables
        self.selected_interface = tk.StringVar(value="interfaces")
        self.selected_module = tk.StringVar(value="modules")
        self.options_list = ["Restart Network Adapter", "Stop Monitor Mode"]
        self.selected_option = tk.StringVar(value="options")

        # Host list variables
        self.packets = 30
        self.filter_text = tk.StringVar(value="")
        self.selected_target = tk.StringVar(value="No target selected")

        # Video variables removed - moved to ControllerGUI

        # Log variables
        self.log_queue = queue.Queue()
        self.is_logging = False

        # Appearance
        self._setup_styles()

        # ======================
        # Root window layout
        # ======================
        # Row 0: header bar   Row 1: tabbed content (Operations / Forensics)
        self.configure(background=self.colors["bg"])
        self.minsize(1200, 760)
        self.grid_rowconfigure(0, weight=0)   # Header
        self.grid_rowconfigure(1, weight=1)   # Tabbed content
        self.grid_columnconfigure(0, weight=1)

        # Header bar (wordmark + subtitle + status)
        self._init_header(row=0)

        # ======================
        # Tabbed shell
        # ======================
        # Operations holds today's full toolset. Forensics is a placeholder
        # slot for the upcoming Digital Forensics module (no backend yet).
        self.notebook = tb.Notebook(self)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        # --- Operations tab: current functional UI ---
        self.operations_tab = tb.Frame(self.notebook)
        self.notebook.add(self.operations_tab, text="  Operations  ")

        self.operations_tab.grid_rowconfigure(0, weight=0)          # control bar
        self.operations_tab.grid_rowconfigure(1, weight=1)          # main content
        self.operations_tab.grid_columnconfigure(0, weight=1, minsize=340)  # host list
        self.operations_tab.grid_columnconfigure(1, weight=2)       # dashboard

        # Functional Components (parent is now the Operations tab)
        self._init_top_bar(self.operations_tab, row=0)
        self._init_host_list(self.operations_tab, row=1, col=0)
        self._init_info_video_terminal_panel(self.operations_tab, row=1, col=1)

        # --- Forensics tab: future module placeholder ---
        self._init_forensics_tab()

        # ======================
        # Setup necessary files
        # ======================

        self._setup_files()

        # ======================
        # Setup message logging
        # ======================

        self._process_log_queue()

        # =====================
        # Call autoscan thread
        # =====================

        self.auto_scan_thread = threading.Thread(target=self._auto_scan_loop, daemon=True)
        self.auto_scan_thread.start()

        # ==============
        # Start Program
        # ==============

        self._log_slow("Welcome to INDRA.")
        self._log_slow("Systems initialized. Ready for action!")

    def _setup_files(self):
        """
        Creates necessary data files if they do not already exist.
        """

        data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)

        self.raw_output_path = os.path.join(data_dir, 'raw_output.txt')	
        open(self.raw_output_path, 'w').close()

        self.scan_results_path = os.path.join(data_dir, 'scan_results.txt')
        open(self.scan_results_path, 'w').close()

        self.sniff_output_path = os.path.join(data_dir, 'sniff_output.log')	
        open(self.sniff_output_path, 'w').close()

        self.json_output_path = os.path.join(data_dir, 'module_input_data.json')
        open(self.json_output_path, 'w').close()

        return
    
    def _setup_styles(self):
        """
        Defines the INDRA design system in one place: a shared color palette,
        a typographic scale, and reusable ttk styles.

        NOTE: This method is UI-only. Fonts exposed as self.label_font /
        self.monospace_font and the "Large.Danger.TButton" / "Large.Success.TButton"
        style *names* are consumed elsewhere in the app, so those names are kept
        stable here even though their appearance is modernized.
        """

        self.styles = tb.Style()

        # ======================
        # Color palette (accent-driven dark cyber dashboard)
        # ======================
        # One place to change the look. Roles, not scattered hex values.
        self.colors = {
            "bg":          "#0d1117",  # app background (deepest)
            "surface":     "#161b22",  # card / panel background
            "surface_alt": "#1c2128",  # inset areas (listbox, entries)
            "border":      "#30363d",  # subtle card borders / dividers
            "text":        "#e6edf3",  # primary text
            "text_muted":  "#8b949e",  # secondary / label text
            "accent":      "#2f81f7",  # INDRA primary accent (actions, focus)
            "accent_dim":  "#1f6feb",  # accent hover / pressed
            "success":     "#238636",  # go / running
            "success_dim": "#2ea043",
            "danger":      "#da3633",  # exploit / stop
            "danger_dim":  "#b62324",
            "warning":     "#d29922",  # scan controls
            "info":        "#39c0c8",  # informational
            "terminal_bg": "#0a0e14",  # log console background
            "terminal_fg": "#3ad07a",  # log console text (green)
        }
        c = self.colors

        # ======================
        # Typographic scale
        # ======================
        # Existing names kept: label_font, monospace_font, exploit_font.
        self.title_font     = font.Font(family="Segoe UI", size=20, weight="bold")
        self.subtitle_font  = font.Font(family="Segoe UI", size=10)
        self.heading_font   = font.Font(family="Segoe UI", size=11, weight="bold")
        self.body_font      = font.Font(family="Segoe UI", size=10)
        self.label_font     = font.Font(family="Consolas", size=10)
        self.monospace_font = font.Font(family="Consolas", size=10)
        self.exploit_font   = font.Font(family="Segoe UI", size=12, weight="bold")

        # ======================
        # Reusable ttk styles
        # ======================

        # Header wordmark + subtitle
        self.style.configure("Header.TFrame", background=c["bg"])
        self.style.configure("Wordmark.TLabel",
                             background=c["bg"], foreground=c["text"],
                             font=self.title_font)
        self.style.configure("Subtitle.TLabel",
                             background=c["bg"], foreground=c["text_muted"],
                             font=self.subtitle_font)
        self.style.configure("Status.TLabel",
                             background=c["bg"], foreground=c["text_muted"],
                             font=self.body_font)

        # Section heading used on control cards
        self.style.configure("CardHeading.TLabel",
                             foreground=c["text_muted"], font=self.heading_font)

        # Muted placeholder / empty-state text
        self.style.configure("Muted.TLabel",
                             foreground=c["text_muted"], font=self.body_font)

        # Primary accent action button (reused by the Execute action)
        self.style.configure("Accent.TButton",
                             background=c["accent"], foreground="#ffffff",
                             focuscolor=c["accent"], font=self.body_font,
                             borderwidth=0, padding=(16, 8))
        self.style.map("Accent.TButton", background=[("active", c["accent_dim"])])

        # ======================
        # Exploit button styles (names preserved, appearance modernized)
        # ======================
        # Was a giant 24pt red block; now a clean, professional accent button.
        self.style.configure("Large.Danger.TButton",
                             background=c["danger"], foreground="#ffffff",
                             focuscolor=c["danger"], font=self.exploit_font,
                             borderwidth=0, padding=(28, 10))
        self.style.map("Large.Danger.TButton", background=[("active", c["danger_dim"])])

        self.style.configure("Large.Success.TButton",
                             background=c["success"], foreground="#ffffff",
                             focuscolor=c["success"], font=self.exploit_font,
                             borderwidth=0, padding=(28, 10))
        self.style.map("Large.Success.TButton", background=[("active", c["success_dim"])])
        
    def _init_header(self, row):
        """
        Creates the application header: INDRA wordmark, subtitle, and a
        right-aligned status indicator. UI-only, no functional bindings.
        """

        header = tb.Frame(self, style="Header.TFrame", padding=(16, 12, 16, 8))
        header.grid(row=row, column=0, sticky="nsew")
        header.grid_columnconfigure(1, weight=1)

        # Wordmark + subtitle (left)
        brand = tb.Frame(header, style="Header.TFrame")
        brand.grid(row=0, column=0, sticky="w")
        tb.Label(brand, text="INDRA", style="Wordmark.TLabel").pack(side=tk.LEFT)
        tb.Label(brand, text="Drone Security Platform",
                 style="Subtitle.TLabel").pack(side=tk.LEFT, padx=(12, 0), pady=(10, 0))

        # Status indicator (right)
        self.status_label = tk.Label(header, text="●  Ready",
                                     background=self.colors["bg"],
                                     foreground=self.colors["success"],
                                     font=self.body_font)
        self.status_label.grid(row=0, column=2, sticky="e")

    def _init_top_bar(self, parent, row):
        """
        Creates the control bar, organized into two grouped cards:
        Scan Controls and Module Controls.

        All widget attribute names, commands, and event bindings are preserved
        exactly from the original single-row layout; only their grouping and
        styling change.
        """

        # ==========
        # GUI Setup
        # ==========

        bar = tb.Frame(parent)
        bar.grid(row=row, column=0, columnspan=2, sticky="nsew", padx=12, pady=(12, 8))
        bar.grid_columnconfigure(0, weight=1)
        bar.grid_columnconfigure(1, weight=2)

        # =====================
        # Scan Controls card
        # =====================

        scan_card = tb.Labelframe(bar, text=" Scan Controls ", bootstyle="warning", padding=10)
        scan_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        # Network Interface Dropdown
        self.interface_dropdown = tb.Combobox(scan_card,
                                     state="readonly",
                                     width=16,
                                     font=self.label_font,
                                     values=self._get_network_interfaces(),
                                     textvariable=self.selected_interface,
                                     bootstyle="warning",
                                     )
        self.interface_dropdown.bind("<<ComboboxSelected>>", self._handle_interface_change)

        # Single Scan Button
        self.scan_btn = tb.Button(scan_card,
                             text="Run Scan",
                             bootstyle='warning-outline',
                             command=self._handle_single_scan
                             )

        # Toggle Scan Button
        self.toggle_btn = tb.Button(scan_card,
                               text="Toggle Scan",
                               bootstyle='warning-outline',
                               command=self._handle_toggle_scan
                               )

        self.interface_dropdown.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.scan_btn.pack(side=tk.LEFT, padx=4)
        self.toggle_btn.pack(side=tk.LEFT, padx=4)

        # =====================
        # Module Controls card
        # =====================

        module_card = tb.Labelframe(bar, text=" Module Controls ", bootstyle="info", padding=10)
        module_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        # Misc Options Dropdown
        self.options_dropdown = tb.Combobox(module_card,
                                        state="readonly",
                                        width=18,
                                        font=self.label_font,
                                        values=self.options_list,
                                        textvariable=self.selected_option,
                                        bootstyle="info"
                                        )
        self.options_dropdown.bind("<<ComboboxSelected>>", self._handle_option_change)

        # Misc Options button
        self.options_btn = tb.Button(module_card,
                                text="Execute Option",
                                bootstyle="info-outline",
                                command=self._handle_option_execute
                                )

        # Flight Deck Button (manual launch)
        self.flight_deck_btn = tb.Button(module_card,
                        text="Flight Deck",
                        bootstyle="primary-outline",
                        command=self._handle_open_controller
                        )

        # Exploit Module Dropdown
        self.exploit_dropdown = tb.Combobox(module_card,
                                    state="readonly",
                                    width=14,
                                    font=self.label_font,
                                    values=self._get_exploit_modules(),
                                    textvariable=self.selected_module,
                                    bootstyle="danger"
                                    )
        self.exploit_dropdown.bind("<<ComboboxSelected>>", self._handle_module_change)

        # Exploit Button (primary destructive action)
        self.exploit_btn = tb.Button(module_card,
                                text="EXPLOIT",
                                style="Large.Danger.TButton",
                                command=self._handle_run_exploit
                                )

        # ================
        # Placing widgets
        # ================

        self.options_dropdown.pack(side=tk.LEFT, padx=(0, 4))
        self.options_btn.pack(side=tk.LEFT, padx=4)
        self.flight_deck_btn.pack(side=tk.LEFT, padx=4)
        tb.Separator(module_card, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        self.exploit_dropdown.pack(side=tk.LEFT, padx=4)
        self.exploit_btn.pack(side=tk.RIGHT, padx=(4, 0))

    # ======================
    # Functions for top bar
    # ======================

    def _handle_toggle_scan(self):
        """
        Handles the scan toggling logic.

        Actual toggle value is sensed by the auto-scanning thread.
        """

        self.scan_toggled = not self.scan_toggled

        self._log(f"Toggle scan state: {self.scan_toggled}")

        if self.scan_toggled:
            self.toggle_btn.config(text="Stop Scanning")
            self.toggle_btn.config(bootstyle="danger-outline")
        else:
            self.toggle_btn.config(text="Start Scanning")
            self.toggle_btn.config(bootstyle="success-outline")
    
    def _auto_scan_loop(self):
        """
        Continuously runs scans in a loop with a cooldown period.
        Runs in a separate thread.
        """

        while True:
            if self.scan_toggled and not self.is_scanning:
                self._handle_single_scan()
            time.sleep(self.auto_scan_cooldown)

    def _interface_is_managed(self, interface):
        """
        Checks whether the given interface is currently in managed mode,
        via `iw dev <interface> info`. Returns False (i.e. "needs reset")
        if the mode can't be determined.
        """

        try:
            output = subprocess.check_output(
                f"iw dev {interface} info", shell=True, text=True, stderr=subprocess.DEVNULL
            )
            for line in output.splitlines():
                stripped = line.strip()
                if stripped.startswith("type "):
                    return stripped.split()[-1] == "managed"
        except Exception:
            pass

        return False

    def _handle_single_scan(self):
        """
        Handles a single scan event.
        """

        interface = self._get_interface()
        if interface is None:
            self._log("Please select network interface first.")
            return -1

        if self.is_scanning:
            self._log("Only one scan can be run at a time.")
            return -1
        
        self.is_scanning = True
        self.scan_btn.configure(text="Scanning...", bootstyle="danger-outline", state=DISABLED)
        
        self._log_slow("Beep boop. Scanning...")

        def _scan_and_exit():
            try:
                # Only bounce the interface into managed mode if it isn't
                # already there (e.g. left in monitor mode by a previous
                # exploit run). Doing this unconditionally before every
                # scan - including every auto-scan tick - added several
                # seconds of interface down/up churn on top of scan()'s
                # own recovery logic, and ran synchronously on the caller's
                # thread (freezing the GUI on a manual "Run Scan" click).
                if not self._interface_is_managed(interface):
                    sudo_exec(f"ifconfig {interface} down")
                    sudo_exec(f"iwconfig {interface} mode managed")
                    sudo_exec(f"ifconfig {interface} up")
                    time.sleep(1)

                scan_result = scan(interface)
                self.is_scanning = False
                self.after(0, lambda: self.scan_btn.configure(text="Run Scan", bootstyle="success-outline", state=NORMAL))

                # Check for special error codes
                if scan_result == SCAN_ERROR_UNSUPPORTED_INTERFACE:
                    self._log(f"Error! Interface '{interface}' does not support wireless scanning.")
                    return
                elif scan_result == SCAN_ERROR_GENERIC:
                    # Try to read the actual error message from raw_output.txt
                    try:
                        raw_output_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw_output.txt")
                        with open(raw_output_path, 'r') as f:
                            error_msg = f.read().strip()
                            if error_msg:
                                self._log(f"Error! Scan failed: {error_msg}")
                            else:
                                self._log("Error! A generic error occurred during scanning.")
                    except:
                        self._log("Error! A generic error occurred during scanning.")
                    return
                
                self.all_targets = scan_result

                if self.all_targets is None or self.all_targets == {}:
                    self._log("Error! Could not find any targets.")
            
                else:
                    self.after(0, self._get_scan_results)
                    self._log_slow("Scan successfully completed!")

            except Exception as e:
                self._log(f"Error! aborting scan: {e}")
                self.is_scanning = False
                self.scan_btn.configure(text="Run Scan", bootstyle="success-outline", state=NORMAL)
                return

        t = threading.Thread(target=_scan_and_exit)
        t.start()

    def _get_scan_results(self):
        """
        Updates scan results to the GUI and backend.
        """

        try:
            with open(self.scan_results_path, 'r') as f:
                for line in f:
                    self.host_listbox.insert(END, line)
        except FileNotFoundError:
            self._log(f"Scan results not found at {self.scan_results_path}.")
        
        self._handle_filter_change()

        return

    def _get_network_interfaces(self)-> list:
        """
        Returns a list of available network interfaces on the system.
        """

        output = subprocess.check_output('ifconfig | cut -d " " -f1', shell=True, text=True).strip()
        return [interface.replace(':', '') for interface in output.splitlines() if interface]
    
    def _handle_interface_change(self, event=None):
        """
        Updates the selected network interface when changed from the dropdown.
        """
        
        selected = self.interface_dropdown.get()
        self.selected_interface.set(selected)

        return

    def _get_exploit_modules(self)-> list:
        """
        Returns a list of available exploit modules.
        """

        modules = module_setup()
        return modules
    
    def _handle_module_change(self, event=None):
        """
        Updates the selected exploit module when changed from the dropdown.
        """
        
        selected = self.exploit_dropdown.get()
        self.selected_module.set(selected)

        return
    
    def _get_target(self)-> str:
        """
        Returns the currently selected target from the host list
        """

        target = None

        try:
            target = self.selected_target.get()
        except Exception:
            self._log("Error retrieving selected target.")
            return "No target selected"
        
        return target
    
    def _extract_mac_address(self, mac_string: str) -> str:
        """
        Extracts a valid MAC address from a string that may contain extra characters.
        
        Args:
            mac_string (str): String that should contain a MAC address
            
        Returns:
            str: Valid MAC address in format XX:XX:XX:XX:XX:XX, or original string if not found
        """
        mac_string = mac_string.strip()
        
        # Look for MAC address pattern (6 pairs of hex digits separated by colons)
        mac_match = re.search(r'([0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2})', mac_string)
        
        if mac_match:
            return mac_match.group(1)
        else:
            return mac_string
    
    def _get_target_info(self, target_name)->list:
        """
        Returns the target info list for the given target name.
        """

        if target_name.strip() in self.all_targets:
            return self.all_targets[target_name.strip()]
        else:
            return ['', '', '', '', '', '']

    def _get_module(self):
        """
        Returns the currently selected exploit module from the dropdown.
        """

        module = self.selected_module.get()
        if module == "modules":
            return None
        
        return module

    def _get_interface(self):
        """
        Returns the currently selected network interface from the dropdown.
        """

        interface = self.selected_interface.get()
        if interface == "interfaces":
            return None
        
        return interface
    
    def _handle_run_exploit(self):
        """
        Executes the selected exploit module against the selected target.
        """

        if self.is_scanning:
            self._log("Please stop scanning before running an exploit.")
            return -1

        target_name = self._get_target()
        if target_name is None:
            self._log("Please select target first.")
            return -1
        
        exploit = self._get_module()
        if exploit is None:
            self._log("Please select exploit module first.")
            return -1

        interface = self._get_interface()
        if interface is None:
            self._log("Please select network interface first.")
            return -1
        
        target_info = self._get_target_info(target_name)
        if target_info is None:
            self._log("Error retrieving target info.")
            return -1

        self.target_info_label.configure(text=	f"Target: {target_name}\n"\
                                                   f"MAC: {target_info[1]}\n"\
                                                f"Quality: {target_info[2]}\n"\
                                                f"Channel: {target_info[3]}\n"\
                                                f"Signal Level: {target_info[4]}\n"\
                                                f"Encryption: {target_info[5]}\n"
                                                )
        self.target_info_label.update()

        target_data = {
            "target_name": target_name.strip(),
            "target_info": {
                "raw_string": target_info[0].strip() if len(target_info) > 0 else "",
                "mac_address": self._extract_mac_address(target_info[1]) if len(target_info) > 1 else "",
                "quality": target_info[2].strip() if len(target_info) > 2 else "",
                "channel": target_info[3].strip() if len(target_info) > 3 else "",
                "signal_level": target_info[4].strip() if len(target_info) > 4 else "",
                "encryption": target_info[5].strip() if len(target_info) > 5 else ""
                },
                
            "options": {
                "packets": self.packets,
                "interface": interface.strip(),
                }
            }
        
        try:
            with open(self.json_output_path, "w") as f:
                json.dump(target_data, f, indent=4)
        except Exception as e:
            self._log(f"Error writing to JSON file: {e}")
            return -1

        exploit_path = os.path.join(os.path.dirname(__file__), "..", "..", "modules", f"{exploit}", f"{exploit}.py")
        src_path = os.path.join(os.path.dirname(__file__), "..", "..", "src")
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{src_path}{os.pathsep}{env.get('PYTHONPATH', '')}"

        self._log_slow(f"Launching exploit: {exploit} on target: {target_name}")
        self.exploit_btn.config(text="RUNNING", state=tk.DISABLED, style="Large.Success.TButton")

        # Signal video monitor to reset file position for new exploit run
        self.video_file_position_reset = True

        def _run_exploit_thread():
            """
            Runs the exploit in a background thread so the GUI can continue functioning.
            """

            try: 
                module_return_code = subprocess.call([sys.executable, exploit_path], env=env)
                self._log_slow(f"Module {exploit} finished with return code: {module_return_code}")
            except Exception as e:
                self._log(f"Error executing module {exploit}: {e}")
                return -1
            # finally:
            #     sudo_exec(f"ifconfig {interface} down")
            #     sudo_exec(f"iwconfig {interface} mode managed")
            #     sudo_exec(f"ifconfig {interface} up")

            self.after(0, lambda: self.exploit_btn.config(text="EXPLOIT", state=tk.NORMAL, style="Large.Danger.TButton"))

        self.exploit_thread = threading.Thread(target=_run_exploit_thread, daemon=True)
        self.exploit_thread.start()

    def _handle_option_execute(self):
        """
        Executes the selected misc option from the dropdown.
        """

        match self.selected_option.get():
            case "Restart Network Adapter":
                self._log_slow("Restarting Network Adapter...")
                sudo_exec("service NetworkManager restart")
            case "Stop Monitor Mode":
                if self.selected_interface.get() == "interfaces":
                    self._log("Please select a network interface first.")
                else:
                    self._log_slow("Stopping Monitor Mode...")
                    sudo_exec(f"airmon-ng stop {self.selected_interface.get()}")
            case _:
                self._log("No option selected or unrecognized option.")
        
        return

    def _handle_option_change(self, event=None):
        """
        Updates the selected option when changed from the dropdown.
        """
        
        selected = self.options_dropdown.get()
        self.selected_option.set(selected)

        return

    def _handle_open_controller(self):
        """
        Manually launches the external flight controller GUI.
        """

        if self.controller_process and self.controller_process.poll() is None:
            self._log("Flight Deck is already running.")
            return

        current_dir = os.path.dirname(os.path.abspath(__file__))
        controller_path = os.path.join(current_dir, "controllerGUI.py")

        if not os.path.exists(controller_path):
            self._log(f"Error! {controller_path} not found.")
            return

        try:
            self.controller_process = subprocess.Popen([sys.executable, controller_path])
            self._log_slow("Opening Flight Deck...")
        except Exception as e:
            self._log(f"Error launching Flight Deck: {e}")
    
    def _init_host_list(self, parent, row, col):
        """
        Creates the host list sidebar: a search field, the discovered-host
        listbox, and an empty-state message. All selection/filter bindings
        are preserved from the original.
        """

        # ==========
        # GUI Setup
        # ==========

        host_list_frame = tb.Labelframe(parent, text=" Host List ", bootstyle="warning", padding=8)
        host_list_frame.grid(row=row, column=col, sticky="nsew", padx=(12, 6), pady=(0, 12))

        # Search bar
        filter_bar = tb.Frame(host_list_frame)
        filter_bar.pack(fill=tk.X, padx=2, pady=(0, 8))

        tb.Label(filter_bar, text="Search", style="CardHeading.TLabel").pack(side=tk.LEFT, padx=(0, 6))

        # Filter box
        self.filter_entry = tb.Entry(filter_bar,
                           bootstyle="warning",
                           font=self.label_font,
                           textvariable=self.filter_text
                           )
        self.filter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.filter_entry.bind("<KeyRelease>", self._handle_filter_change)

        # Frame for Host Listbox (also hosts the empty-state overlay)
        listbox_frame = tb.Frame(host_list_frame)
        listbox_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Host Listbox
        self.host_listbox = tk.Listbox(listbox_frame,
                                 bg=self.colors["surface_alt"],
                                 fg=self.colors["text"],
                                 font=self.monospace_font,
                                 selectbackground=self.colors["accent"],
                                 selectforeground="#ffffff",
                                 borderwidth=0,
                                 relief="flat",
                                 highlightthickness=1,
                                 highlightbackground=self.colors["border"],
                                 activestyle="none"
                                 )
        self.host_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.host_listbox.bind("<<ListboxSelect>>", self._handle_host_selection)

        # Scrollbar for Host Listbox
        scrollbar = tb.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.host_listbox.yview, bootstyle="warning-round")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.host_listbox.config(yscrollcommand=scrollbar.set)

        # Empty-state overlay (shown when no hosts are present)
        self.host_empty_label = tk.Label(listbox_frame,
                                    text="No hosts discovered —\nrun a scan to begin.",
                                    bg=self.colors["surface_alt"],
                                    fg=self.colors["text_muted"],
                                    font=self.body_font,
                                    justify=tk.CENTER)
        self._update_host_empty_state()

    # ========================
    # Functions for host list
    # ========================

    def _handle_filter_change(self, event=None):
        """
        Updates the host list based on the filter text.
        """

        query = self.filter_text.get()

        self.host_listbox.delete(0, END)

        if query.strip() == "":
            for host in self.all_targets:
                self.host_listbox.insert(END, host)
        else:
            for host in self.all_targets:
                if query in host:
                    self.host_listbox.insert(END, host)

        # Refresh the empty-state overlay to match current list contents
        self._update_host_empty_state()

        return

    def _update_host_empty_state(self):
        """
        UI-only: shows the "no hosts" overlay when the listbox is empty and
        hides it once hosts are present. Does not alter any host data.
        """

        if self.host_listbox.size() == 0:
            self.host_empty_label.place(relx=0.5, rely=0.5, anchor="center")
        else:
            self.host_empty_label.place_forget()

        return

    def _handle_host_selection(self, event=None):
        """
        Updates the UI when a host is selected from the listbox.
        """

        try:
            selection = self.host_listbox.curselection()
            if not selection:
                self.selected_target.set("No target selected")
                return
            index = selection[0]
            self.selected_target.set(self.host_listbox.get(index))
        except Exception:
            self.selected_target.set("No target selected")
            return

        target_name = self.selected_target.get()

        target_info = self._get_target_info(target_name)
        if target_info is None:
            self._log("Error retrieving target info.")
            self.target_info_label.configure(text= "Target: No target selected")
            self.target_info_label.update()
            return

        self.target_info_label.configure(text=	f"Target: {target_name}\n"\
                                                   f"MAC: {target_info[1]}\n"\
                                                f"Quality: {target_info[2]}\n"\
                                                f"Channel: {target_info[3]}\n"\
                                                f"Signal Level: {target_info[4]}\n"\
                                                f"Encryption: {target_info[5]}\n"
                                                )
        self.target_info_label.update()

        return
    
    def _init_info_video_terminal_panel(self, parent, row, col):
        """
        Creates the right-hand information dashboard: a Target card (details of
        the currently selected host) stacked above a terminal-style System
        Activity log. The self.target_info_label and self.text_terminal widget
        names are preserved so all existing update/logging code keeps working.
        """

        # ==========
        # GUI Setup
        # ==========

        right_panel_frame = tb.Frame(parent)
        right_panel_frame.grid(row=row, column=col, sticky="nsew", padx=(6, 12), pady=(0, 12))

        right_panel_frame.grid_columnconfigure(0, weight=1)
        right_panel_frame.grid_rowconfigure(0, weight=0)   # Target card
        right_panel_frame.grid_rowconfigure(1, weight=1)   # Log console (expands)

        # =====================
        # Target card
        # =====================

        target_card = tb.Labelframe(right_panel_frame, text=" Target ", bootstyle="info", padding=12)
        target_card.grid(row=0, column=0, sticky="new", pady=(0, 8))

        self.target_info_label = tb.Label(target_card,
                                        text="Target: No target selected",
                                        font=self.label_font,
                                        bootstyle="light",
                                        justify=tk.LEFT
                                        )
        self.target_info_label.pack(anchor="w")

        # Video section moved to Controller GUI

        # =====================
        # System Activity log (terminal-style console)
        # =====================

        terminal_frame = tb.Labelframe(right_panel_frame, text=" System Activity ", padding=8, bootstyle="info")
        terminal_frame.grid(row=1, column=0, sticky="nsew")

        # Terminal Window
        self.text_terminal = tk.Text(terminal_frame,
                               wrap=tk.WORD,
                               font=self.monospace_font,
                               bg=self.colors["terminal_bg"],
                               fg=self.colors["terminal_fg"],
                               insertbackground=self.colors["terminal_fg"],
                               state=tk.DISABLED,
                               relief="flat",
                               borderwidth=0,
                               highlightthickness=0,
                               padx=10,
                               pady=8
                               )
        self.text_terminal.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar for Terminal Window
        terminal_scrollbar = tb.Scrollbar(terminal_frame, orient=tk.VERTICAL, command=self.text_terminal.yview, bootstyle="info-round")
        terminal_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_terminal.config(yscrollcommand=terminal_scrollbar.set)

    def _init_forensics_tab(self):
        """
        Forensics tab.

        The Acquisition card is interactive — it runs the wired USB extraction
        module (forensics/acquisition/usb_extractor.py) and shows real results.
        The remaining five cards are still visual placeholders for future work.
        """

        self.forensics_tab = tb.Frame(self.notebook)
        self.notebook.add(self.forensics_tab, text="  Forensics  ")

        # Scrollable area: a canvas + always-visible scrollbar with an inner
        # frame, so all six (tall) cards stay reachable on any window size.
        # Manual implementation for reliability across ttkbootstrap versions and
        # on Linux (the VM), where wheel events arrive as Button-4 / Button-5.
        fx_canvas = tk.Canvas(self.forensics_tab, background=self.colors["bg"],
                              highlightthickness=0)
        fx_vbar = tb.Scrollbar(self.forensics_tab, orient=tk.VERTICAL,
                               command=fx_canvas.yview, bootstyle="round")
        fx_canvas.configure(yscrollcommand=fx_vbar.set)
        fx_vbar.pack(side=tk.RIGHT, fill=tk.Y)
        fx_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        container = tb.Frame(fx_canvas, padding=20)
        fx_window = fx_canvas.create_window((0, 0), window=container, anchor="nw")

        # Keep the scrollregion and inner width synced with content / canvas.
        container.bind("<Configure>",
                       lambda e: fx_canvas.configure(scrollregion=fx_canvas.bbox("all")))
        fx_canvas.bind("<Configure>",
                       lambda e: fx_canvas.itemconfigure(fx_window, width=e.width))

        # Mouse-wheel scrolling (Windows/macOS: MouseWheel; Linux/VM: Button-4/5).
        def _fx_wheel(event):
            if getattr(event, "num", None) == 4:
                fx_canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                fx_canvas.yview_scroll(1, "units")
            elif getattr(event, "delta", 0):
                fx_canvas.yview_scroll(int(-event.delta / 120), "units")

        def _fx_bind_wheel(_):
            fx_canvas.bind_all("<MouseWheel>", _fx_wheel)
            fx_canvas.bind_all("<Button-4>", _fx_wheel)
            fx_canvas.bind_all("<Button-5>", _fx_wheel)

        def _fx_unbind_wheel(_):
            fx_canvas.unbind_all("<MouseWheel>")
            fx_canvas.unbind_all("<Button-4>")
            fx_canvas.unbind_all("<Button-5>")

        fx_canvas.bind("<Enter>", _fx_bind_wheel)
        fx_canvas.bind("<Leave>", _fx_unbind_wheel)

        tb.Label(container, text="Digital Forensics",
                 style="CardHeading.TLabel").pack(anchor="w")
        tb.Label(container,
                 text="Post-capture forensic analysis of a captured drone.",
                 style="Muted.TLabel").pack(anchor="w", pady=(4, 16))

        # ---- All six cards in one uniform 2-column grid ----
        # Row 0: the two working cards (Acquisition, Integrity), kept fully
        # functional. Rows below: placeholder cards for future work.
        grid = tb.Frame(container)
        grid.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        grid.grid_columnconfigure(0, weight=1, uniform="fx")
        grid.grid_columnconfigure(1, weight=1, uniform="fx")

        # Working cards (interactive)
        self._init_acquisition_card(grid, row=0, col=0)
        self._init_integrity_card(grid, row=0, col=1)
        self._init_reporting_card(grid, row=1, col=0)

        # ---- Analysis cards (interactive) ----
        # Each runs a forensics/analysis pass over a session and shows findings.
        self.fl_card = self._make_analysis_card(
            grid, 1, 1, "Flight Logs / Telemetry",
            "Parse extracted DJI flight logs (.TXT readable; .DAT binary header).",
            "Parse Logs", self._handle_flight_logs)
        self.mm_card = self._make_analysis_card(
            grid, 2, 0, "Media Metadata",
            "Extract EXIF / image metadata (camera, timestamp, GPS) from media.",
            "Extract Metadata", self._handle_media_metadata)
        self.steg_card = self._make_analysis_card(
            grid, 2, 1, "Steganography",
            "Scan images for hidden / appended data and embedded file signatures.",
            "Scan Images", self._handle_steganography)

    def _init_acquisition_card(self, parent, row=0, col=0):
        """
        Interactive Acquisition card: runs the wired USB extraction module in a
        background thread and displays the real manifest results.

        Widget state used by the handlers:
            self.acq_source_var    - source path entry (blank = auto-detect)
            self.acq_run_btn       - the Run Extraction button
            self.acq_status_label  - one-line status
            self.acq_results       - read-only results text area
            self.acq_running       - guard flag against concurrent runs
        """

        self.acq_running = False

        card = tb.Labelframe(parent, text=" Acquisition — Wired (USB) Extraction ",
                             bootstyle="info", padding=12)
        card.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)

        tb.Label(card,
                 text="Extract data off a connected DJI drive over USB. Leave the "
                      "source blank to auto-detect, or enter an already-mounted "
                      "path to extract from it directly (useful for testing).",
                 style="Muted.TLabel", wraplength=360, justify=tk.LEFT).pack(anchor="w")

        # Controls: source entry + run button
        controls = tb.Frame(card)
        controls.pack(fill=tk.X, pady=(10, 8))

        tb.Label(controls, text="Source",
                 style="CardHeading.TLabel").pack(side=tk.LEFT, padx=(0, 6))

        self.acq_source_var = tk.StringVar(value="")
        self.acq_source_entry = tb.Entry(controls, bootstyle="info",
                                         font=self.label_font,
                                         textvariable=self.acq_source_var)
        self.acq_source_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        tb.Label(controls, text="(blank = auto-detect)",
                 style="Muted.TLabel").pack(side=tk.LEFT, padx=(0, 8))

        self.acq_run_btn = tb.Button(controls, text="Run Extraction",
                                     bootstyle="info",
                                     command=self._handle_run_acquisition)
        self.acq_run_btn.pack(side=tk.LEFT)

        # Status line
        self.acq_status_label = tb.Label(card, text="Status: idle",
                                         style="Muted.TLabel")
        self.acq_status_label.pack(anchor="w", pady=(0, 6))

        # Results area (read-only)
        results_frame = tb.Frame(card)
        results_frame.pack(fill=tk.BOTH, expand=True)

        self.acq_results = tk.Text(results_frame, height=9, wrap=tk.WORD,
                                   font=self.monospace_font,
                                   bg=self.colors["surface_alt"],
                                   fg=self.colors["text"],
                                   relief="flat", borderwidth=0,
                                   highlightthickness=1,
                                   highlightbackground=self.colors["border"],
                                   state=tk.DISABLED, padx=8, pady=6)
        self.acq_results.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        acq_scroll = tb.Scrollbar(results_frame, orient=tk.VERTICAL,
                                  command=self.acq_results.yview,
                                  bootstyle="info-round")
        acq_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.acq_results.config(yscrollcommand=acq_scroll.set)

        self._set_acq_results("No extraction run yet. Connect a drive (or enter a "
                              "mounted path) and click Run Extraction.")

    # ==============================
    # Functions for acquisition card
    # ==============================

    def _set_acq_results(self, text):
        """Replace the read-only results text area contents."""
        self.acq_results.config(state=tk.NORMAL)
        self.acq_results.delete("1.0", tk.END)
        self.acq_results.insert(tk.END, text)
        self.acq_results.config(state=tk.DISABLED)

    def _handle_run_acquisition(self):
        """
        Kick off USB extraction in a background thread so the GUI stays
        responsive. The worker only computes; all widget updates are marshalled
        back to the GUI thread via self.after().
        """

        if self.acq_running:
            self._log("Extraction already in progress.")
            return

        source = self.acq_source_var.get().strip()
        sources = [source] if source else None

        # In-progress UI state
        self.acq_running = True
        self.acq_run_btn.config(state=tk.DISABLED)
        self.acq_status_label.config(text="Status: extracting...")
        self._set_acq_results("Extraction in progress...")

        if source:
            self._log_slow(f"Starting USB extraction from: {source}")
        else:
            self._log_slow("Starting USB extraction (auto-detect)...")

        def _worker():
            result = {"ok": False, "manifest": None, "output_root": None, "error": None}
            try:
                # Imported here so a missing module never blocks GUI startup.
                from forensics.acquisition import USBExtractor
                extractor = USBExtractor()
                manifest = extractor.extract(sources=sources)
                result["ok"] = True
                result["manifest"] = manifest
                result["output_root"] = extractor.output_root
            except Exception as e:
                result["error"] = str(e)
            # Hand results back to the GUI thread.
            self.after(0, lambda: self._finish_acquisition(result))

        threading.Thread(target=_worker, daemon=True).start()

    def _finish_acquisition(self, result):
        """Runs on the GUI thread: update the card + log from the worker result."""

        self.acq_running = False
        self.acq_run_btn.config(state=tk.NORMAL)

        # --- Hard failure (exception in the extractor) ---
        if not result["ok"]:
            err = result["error"] or "unknown error"
            self.acq_status_label.config(text="Status: failed")
            self._set_acq_results(f"Extraction failed:\n{err}")
            self._log(f"ERROR: USB extraction failed: {err}")
            return

        manifest = result["manifest"] or {}
        summary = manifest.get("summary", {})
        counts = summary.get("counts", {})
        total = summary.get("total_files", 0)
        errcount = summary.get("error_count", 0)
        session = manifest.get("session_id", "?")
        manifest_path = os.path.join(result["output_root"] or "", "manifest.json")

        # --- Build the results readout ---
        lines = [
            f"Session ID : {session}",
            f"Files      : {total}  "
            f"(flight_logs {counts.get('flight_logs', 0)}, "
            f"media {counts.get('media', 0)}, "
            f"other {counts.get('other', 0)})",
            f"Errors     : {errcount}",
            f"Manifest   : {manifest_path}",
        ]
        if errcount:
            lines.append("")
            lines.append("Errors (first 10):")
            for e in manifest.get("errors", [])[:10]:
                lines.append(f"  - {e.get('path', '?')}: {e.get('error', '')}")

        self._set_acq_results("\n".join(lines))

        # --- Status + System Activity log ---
        if total == 0:
            self.acq_status_label.config(text="Status: no data found")
            self._log("No drone/USB storage found to extract from. "
                      "Connect a drive or enter a mounted path.")
        else:
            self.acq_status_label.config(text=f"Status: complete - {total} files")
            self._log_slow(f"USB extraction complete: {total} files "
                           f"({errcount} error(s)). Session {session}.")

    def _init_integrity_card(self, parent, row=0, col=1):
        """
        Interactive Integrity card: re-hashes the files from an extraction
        session and compares them against the manifest's stored SHA-256 values
        to detect tampering or missing files (chain-of-custody re-validation).

        Widget state used by the handlers:
            self.integ_source_var    - session folder / manifest path (blank = latest)
            self.integ_verify_btn    - the Verify Integrity button
            self.integ_status_label  - one-line status
            self.integ_results       - read-only results text area
            self.integ_running       - guard flag against concurrent runs
        """

        self.integ_running = False

        card = tb.Labelframe(parent, text=" Integrity - SHA-256 Verification ",
                             bootstyle="info", padding=12)
        card.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)

        tb.Label(card,
                 text="Re-hash the files from an extraction session and compare "
                      "against the manifest to detect tampering or missing files. "
                      "Leave the session blank to verify the most recent "
                      "extraction, or enter a session folder / manifest.json path.",
                 style="Muted.TLabel", wraplength=360, justify=tk.LEFT).pack(anchor="w")

        # Controls: session entry + verify button
        controls = tb.Frame(card)
        controls.pack(fill=tk.X, pady=(10, 8))

        tb.Label(controls, text="Session",
                 style="CardHeading.TLabel").pack(side=tk.LEFT, padx=(0, 6))

        self.integ_source_var = tk.StringVar(value="")
        self.integ_source_entry = tb.Entry(controls, bootstyle="info",
                                           font=self.label_font,
                                           textvariable=self.integ_source_var)
        self.integ_source_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        tb.Label(controls, text="(blank = most recent)",
                 style="Muted.TLabel").pack(side=tk.LEFT, padx=(0, 8))

        self.integ_verify_btn = tb.Button(controls, text="Verify Integrity",
                                          bootstyle="info",
                                          command=self._handle_verify_integrity)
        self.integ_verify_btn.pack(side=tk.LEFT)

        # Status line
        self.integ_status_label = tb.Label(card, text="Status: idle",
                                           style="Muted.TLabel")
        self.integ_status_label.pack(anchor="w", pady=(0, 6))

        # Results area (read-only)
        results_frame = tb.Frame(card)
        results_frame.pack(fill=tk.BOTH, expand=True)

        self.integ_results = tk.Text(results_frame, height=9, wrap=tk.WORD,
                                     font=self.monospace_font,
                                     bg=self.colors["surface_alt"],
                                     fg=self.colors["text"],
                                     relief="flat", borderwidth=0,
                                     highlightthickness=1,
                                     highlightbackground=self.colors["border"],
                                     state=tk.DISABLED, padx=8, pady=6)
        self.integ_results.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        integ_scroll = tb.Scrollbar(results_frame, orient=tk.VERTICAL,
                                    command=self.integ_results.yview,
                                    bootstyle="info-round")
        integ_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.integ_results.config(yscrollcommand=integ_scroll.set)

        self._set_integrity_results("No verification run yet. Run an extraction "
                                    "first, then verify it here.")

    # ============================
    # Functions for integrity card
    # ============================

    def _set_integrity_results(self, text):
        """Replace the read-only integrity results text area contents."""
        self.integ_results.config(state=tk.NORMAL)
        self.integ_results.delete("1.0", tk.END)
        self.integ_results.insert(tk.END, text)
        self.integ_results.config(state=tk.DISABLED)

    def _resolve_manifest_path(self, target):
        """
        Resolve which manifest.json to verify.

        target may be a manifest.json file, a session folder containing one, or
        blank (=> newest session under data/extracted/). Raises FileNotFoundError
        with a clear message if none is found.
        """

        if target:
            if os.path.isfile(target):
                return target
            candidate = os.path.join(target, "manifest.json")
            if os.path.isfile(candidate):
                return candidate
            raise FileNotFoundError(f"No manifest.json found at: {target}")

        extracted_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "data", "extracted"))
        if not os.path.isdir(extracted_dir):
            raise FileNotFoundError(
                "No extractions found yet (data/extracted is empty). "
                "Run an extraction first.")

        manifests = []
        for name in os.listdir(extracted_dir):
            mp = os.path.join(extracted_dir, name, "manifest.json")
            if os.path.isfile(mp):
                manifests.append(mp)
        if not manifests:
            raise FileNotFoundError(
                "No manifest.json found under data/extracted. Run an extraction first.")

        manifests.sort(key=lambda p: os.path.getmtime(p))
        return manifests[-1]

    def _handle_verify_integrity(self):
        """
        Re-verify a session's SHA-256 hashes in a background thread. The worker
        only computes; all widget updates are marshalled back via self.after().
        """

        if self.integ_running:
            self._log("Integrity check already in progress.")
            return

        target = self.integ_source_var.get().strip()

        self.integ_running = True
        self.integ_verify_btn.config(state=tk.DISABLED)
        self.integ_status_label.config(text="Status: verifying...")
        self._set_integrity_results("Verifying...")
        self._log_slow("Starting SHA-256 integrity verification...")

        def _worker():
            result = {"ok": False, "error": None, "manifest_path": None,
                      "total": 0, "verified": 0, "tampered": 0, "missing": 0,
                      "issues": []}
            try:
                manifest_path = self._resolve_manifest_path(target)
                result["manifest_path"] = manifest_path
                with open(manifest_path) as f:
                    manifest = json.load(f)

                # Reuse the extractor's hashing so verification matches extraction.
                from forensics.acquisition import USBExtractor

                for entry in manifest.get("files", []):
                    path = entry.get("copied_path")
                    expected = entry.get("sha256")
                    result["total"] += 1

                    if not path or not os.path.exists(path):
                        result["missing"] += 1
                        result["issues"].append(("MISSING", path or "?"))
                        continue
                    try:
                        actual = USBExtractor.sha256_file(path)
                    except Exception as e:
                        result["missing"] += 1
                        result["issues"].append(("UNREADABLE", f"{path}: {e}"))
                        continue

                    if actual == expected:
                        result["verified"] += 1
                    else:
                        result["tampered"] += 1
                        result["issues"].append(("TAMPERED", path))

                result["ok"] = True
            except Exception as e:
                result["error"] = str(e)

            self.after(0, lambda: self._finish_integrity(result))

        threading.Thread(target=_worker, daemon=True).start()

    def _finish_integrity(self, result):
        """Runs on the GUI thread: update the integrity card + log the outcome."""

        self.integ_running = False
        self.integ_verify_btn.config(state=tk.NORMAL)

        if not result["ok"]:
            err = result["error"] or "unknown error"
            self.integ_status_label.config(text="Status: failed")
            self._set_integrity_results(f"Integrity check failed:\n{err}")
            self._log(f"ERROR: Integrity check failed: {err}")
            return

        total = result["total"]
        ver = result["verified"]
        tam = result["tampered"]
        mis = result["missing"]

        lines = [
            f"Manifest : {result['manifest_path']}",
            f"Files    : {total}",
            f"Verified : {ver}",
            f"Tampered : {tam}",
            f"Missing  : {mis}",
        ]
        if result["issues"]:
            lines.append("")
            lines.append("Issues (first 15):")
            for kind, path in result["issues"][:15]:
                lines.append(f"  [{kind}] {path}")
        self._set_integrity_results("\n".join(lines))

        if total == 0:
            self.integ_status_label.config(text="Status: nothing to verify")
            self._log("Integrity: manifest listed no files.")
        elif tam == 0 and mis == 0:
            self.integ_status_label.config(text=f"Status: all {ver} files verified")
            self._log_slow(f"Integrity: all {ver} files verified OK.")
        else:
            self.integ_status_label.config(
                text=f"Status: {tam} tampered, {mis} missing")
            self._log(f"WARNING: Integrity issues - {tam} tampered, {mis} missing.")

    def _init_reporting_card(self, parent, row=1, col=0):
        """
        Interactive Reporting card: generates a forensic summary report for an
        extraction session (file inventory + SHA-256 integrity result) and saves
        it as report.txt next to the session's manifest.

        Widget state used by the handlers:
            self.report_source_var    - session folder / manifest path (blank = latest)
            self.report_btn           - the Generate Report button
            self.report_status_label  - one-line status
            self.report_results       - read-only report preview area
            self.report_running       - guard flag against concurrent runs
        """

        self.report_running = False

        card = tb.Labelframe(parent, text=" Reporting - Forensic Summary ",
                             bootstyle="info", padding=12)
        card.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)

        tb.Label(card,
                 text="Generate a forensic summary report for an extraction "
                      "session (file inventory + SHA-256 integrity). Leave the "
                      "session blank for the most recent extraction, or enter a "
                      "session folder / manifest.json path. Saved as report.txt.",
                 style="Muted.TLabel", wraplength=360, justify=tk.LEFT).pack(anchor="w")

        # Controls: session entry + generate button
        controls = tb.Frame(card)
        controls.pack(fill=tk.X, pady=(10, 8))

        tb.Label(controls, text="Session",
                 style="CardHeading.TLabel").pack(side=tk.LEFT, padx=(0, 6))

        self.report_source_var = tk.StringVar(value="")
        self.report_source_entry = tb.Entry(controls, bootstyle="info",
                                            font=self.label_font,
                                            textvariable=self.report_source_var)
        self.report_source_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        tb.Label(controls, text="(blank = most recent)",
                 style="Muted.TLabel").pack(side=tk.LEFT, padx=(0, 8))

        self.report_btn = tb.Button(controls, text="Generate Report",
                                    bootstyle="info",
                                    command=self._handle_generate_report)
        self.report_btn.pack(side=tk.LEFT)

        # Status line
        self.report_status_label = tb.Label(card, text="Status: idle",
                                            style="Muted.TLabel")
        self.report_status_label.pack(anchor="w", pady=(0, 6))

        # Report preview area (read-only)
        results_frame = tb.Frame(card)
        results_frame.pack(fill=tk.BOTH, expand=True)

        self.report_results = tk.Text(results_frame, height=9, wrap=tk.WORD,
                                      font=self.monospace_font,
                                      bg=self.colors["surface_alt"],
                                      fg=self.colors["text"],
                                      relief="flat", borderwidth=0,
                                      highlightthickness=1,
                                      highlightbackground=self.colors["border"],
                                      state=tk.DISABLED, padx=8, pady=6)
        self.report_results.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        report_scroll = tb.Scrollbar(results_frame, orient=tk.VERTICAL,
                                     command=self.report_results.yview,
                                     bootstyle="info-round")
        report_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.report_results.config(yscrollcommand=report_scroll.set)

        self._set_report_results("No report generated yet. Run an extraction "
                                "first, then generate a report here.")

    # ============================
    # Functions for reporting card
    # ============================

    def _set_report_results(self, text):
        """Replace the read-only report preview area contents."""
        self.report_results.config(state=tk.NORMAL)
        self.report_results.delete("1.0", tk.END)
        self.report_results.insert(tk.END, text)
        self.report_results.config(state=tk.DISABLED)

    def _verify_session(self, manifest):
        """
        Re-hash a manifest's files and return
        (total, verified, tampered, missing, issues) for the report.
        """
        from forensics.acquisition import USBExtractor

        total = ver = tam = mis = 0
        issues = []
        for entry in manifest.get("files", []):
            path = entry.get("copied_path")
            expected = entry.get("sha256")
            total += 1
            if not path or not os.path.exists(path):
                mis += 1
                issues.append(("MISSING", path or "?"))
                continue
            try:
                actual = USBExtractor.sha256_file(path)
            except Exception as e:
                mis += 1
                issues.append(("UNREADABLE", f"{path}: {e}"))
                continue
            if actual == expected:
                ver += 1
            else:
                tam += 1
                issues.append(("TAMPERED", path))
        return total, ver, tam, mis, issues

    def _build_report_text(self, manifest, manifest_path, integ):
        """Render the plain-text forensic report from a manifest + integrity result."""
        total, ver, tam, mis, issues = integ
        s = manifest.get("summary", {})
        counts = s.get("counts", {})

        lines = []
        add = lines.append
        bar = "=" * 60

        add(bar)
        add(" INDRA DIGITAL FORENSICS - EXTRACTION REPORT")
        add(bar)
        add(f"Session ID     : {manifest.get('session_id', '?')}")
        add(f"Report time    : {datetime.now(timezone.utc).isoformat()}")
        add(f"Extraction     : {manifest.get('extraction_started', '?')} -> "
            f"{manifest.get('extraction_completed', '?')}")
        add(f"Host           : {manifest.get('host', '')}")
        add(f"DJI detected   : {manifest.get('dji_device_detected')}")
        add(f"Manifest       : {manifest_path}")
        add("")

        add("--- SOURCES ---")
        sources = manifest.get("sources", [])
        for src in sources:
            add(f"  {src.get('label', '?')} @ {src.get('mountpoint', '?')} "
                f"({src.get('fstype') or '?'}, {src.get('size') or '?'})")
        if not sources:
            add("  (none recorded)")
        add("")

        add("--- FILE SUMMARY ---")
        add(f"  Total files  : {s.get('total_files', 0)} "
            f"({s.get('total_bytes', 0)} bytes)")
        add(f"  Flight logs  : {counts.get('flight_logs', 0)}")
        add(f"  Media        : {counts.get('media', 0)}")
        add(f"  Other        : {counts.get('other', 0)}")
        add("")

        add("--- INTEGRITY (SHA-256 re-verification) ---")
        add(f"  Verified     : {ver}")
        add(f"  Tampered     : {tam}")
        add(f"  Missing      : {mis}")
        if total == 0:
            add("  Result       : (no files)")
        elif tam == 0 and mis == 0:
            add("  Result       : PASS - all files intact")
        else:
            add("  Result       : FAIL - integrity issues detected")
        if issues:
            add("  Issues:")
            for kind, path in issues[:50]:
                add(f"    [{kind}] {path}")
        add("")

        # Per-category file inventory
        for cat, title in (("flight_logs", "FLIGHT LOGS"),
                           ("media", "MEDIA"),
                           ("other", "OTHER")):
            entries = [e for e in manifest.get("files", []) if e.get("category") == cat]
            add(f"--- {title} ({len(entries)}) ---")
            for e in entries:
                sha = (e.get("sha256") or "")[:16]
                add(f"  {e.get('relative_path', '?')}  [{e.get('file_type', '?')}]  "
                    f"{e.get('size_bytes', 0)}b  sha256:{sha}...")
            if not entries:
                add("  (none)")
            add("")

        errs = manifest.get("errors", [])
        add(f"--- EXTRACTION ERRORS ({len(errs)}) ---")
        for er in errs[:50]:
            add(f"  {er.get('path', '?')}: {er.get('error', '')}")
        if not errs:
            add("  (none)")
        add("")
        add(bar)
        add(" END OF REPORT")
        add(bar)
        return "\n".join(lines)

    def _handle_generate_report(self):
        """
        Generate a forensic report in a background thread. The worker only
        computes; all widget updates are marshalled back via self.after().
        """

        if self.report_running:
            self._log("Report already generating.")
            return

        target = self.report_source_var.get().strip()

        self.report_running = True
        self.report_btn.config(state=tk.DISABLED)
        self.report_status_label.config(text="Status: generating...")
        self._set_report_results("Generating report...")
        self._log_slow("Generating forensic report...")

        def _worker():
            result = {"ok": False, "error": None, "report_path": None, "text": None}
            try:
                manifest_path = self._resolve_manifest_path(target)
                with open(manifest_path) as f:
                    manifest = json.load(f)
                integ = self._verify_session(manifest)
                text = self._build_report_text(manifest, manifest_path, integ)

                report_path = os.path.join(os.path.dirname(manifest_path), "report.txt")
                with open(report_path, "w") as f:
                    f.write(text)

                result["ok"] = True
                result["report_path"] = report_path
                result["text"] = text
            except Exception as e:
                result["error"] = str(e)

            self.after(0, lambda: self._finish_report(result))

        threading.Thread(target=_worker, daemon=True).start()

    def _finish_report(self, result):
        """Runs on the GUI thread: show the report preview + log the outcome."""

        self.report_running = False
        self.report_btn.config(state=tk.NORMAL)

        if not result["ok"]:
            err = result["error"] or "unknown error"
            self.report_status_label.config(text="Status: failed")
            self._set_report_results(f"Report generation failed:\n{err}")
            self._log(f"ERROR: Report generation failed: {err}")
            return

        self._set_report_results(result["text"])
        self.report_status_label.config(text="Status: report saved")
        self._log_slow(f"Forensic report saved: {result['report_path']}")

    # =========================================
    # Generic analysis cards (Flight Logs /
    # Media Metadata / Steganography)
    # =========================================
    # These three cards share the same shape (session entry + run button +
    # status + results) and the same run/finish flow, so they're built from a
    # single helper and driven by a small per-card state dict.

    def _make_analysis_card(self, parent, row, col, title, desc, button_text, command):
        """
        Build one interactive analysis card and return its state dict:
            {"src_var", "btn", "status", "results", "running"}.
        """
        card = tb.Labelframe(parent, text=f" {title} ", bootstyle="info", padding=12)
        card.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)

        tb.Label(card, text=desc, style="Muted.TLabel",
                 wraplength=360, justify=tk.LEFT).pack(anchor="w")

        controls = tb.Frame(card)
        controls.pack(fill=tk.X, pady=(10, 8))
        tb.Label(controls, text="Session",
                 style="CardHeading.TLabel").pack(side=tk.LEFT, padx=(0, 6))

        src_var = tk.StringVar(value="")
        entry = tb.Entry(controls, bootstyle="info", font=self.label_font,
                         textvariable=src_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        tb.Label(controls, text="(blank = most recent)",
                 style="Muted.TLabel").pack(side=tk.LEFT, padx=(0, 8))

        btn = tb.Button(controls, text=button_text, bootstyle="info", command=command)
        btn.pack(side=tk.LEFT)

        status = tb.Label(card, text="Status: idle", style="Muted.TLabel")
        status.pack(anchor="w", pady=(0, 6))

        results_frame = tb.Frame(card)
        results_frame.pack(fill=tk.BOTH, expand=True)
        results = tk.Text(results_frame, height=8, wrap=tk.WORD,
                          font=self.monospace_font,
                          bg=self.colors["surface_alt"], fg=self.colors["text"],
                          relief="flat", borderwidth=0, highlightthickness=1,
                          highlightbackground=self.colors["border"],
                          state=tk.DISABLED, padx=8, pady=6)
        results.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = tb.Scrollbar(results_frame, orient=tk.VERTICAL,
                              command=results.yview, bootstyle="info-round")
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        results.config(yscrollcommand=scroll.set)

        state = {"src_var": src_var, "btn": btn, "status": status,
                 "results": results, "running": False}
        self._set_text(results, "No analysis run yet. Run an extraction first, "
                                "then run this analysis.")
        return state

    def _set_text(self, widget, text):
        """Replace a read-only Text widget's contents."""
        widget.config(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, text)
        widget.config(state=tk.DISABLED)

    def _run_analysis(self, state, label, analyze_fn, out_name, formatter):
        """
        Shared runner for the analysis cards. Runs analyze_fn(manifest_path) in a
        background thread, writes its result JSON into the session folder, and
        updates the card via self.after().
        """
        if state["running"]:
            self._log(f"{label} already running.")
            return

        target = state["src_var"].get().strip()
        state["running"] = True
        state["btn"].config(state=tk.DISABLED)
        state["status"].config(text="Status: analyzing...")
        self._set_text(state["results"], "Analyzing...")
        self._log_slow(f"{label}: starting...")

        def _worker():
            result = {"ok": False, "error": None, "data": None, "out_path": None}
            try:
                manifest_path = self._resolve_manifest_path(target)
                data = analyze_fn(manifest_path)
                out_path = os.path.join(os.path.dirname(manifest_path), out_name)
                with open(out_path, "w") as f:
                    json.dump(data, f, indent=2)
                result["ok"] = True
                result["data"] = data
                result["out_path"] = out_path
            except Exception as e:
                result["error"] = str(e)
            self.after(0, lambda: self._finish_analysis(state, label, result, formatter))

        threading.Thread(target=_worker, daemon=True).start()

    def _finish_analysis(self, state, label, result, formatter):
        """Runs on the GUI thread: render analysis findings + log the outcome."""
        state["running"] = False
        state["btn"].config(state=tk.NORMAL)

        if not result["ok"]:
            err = result["error"] or "unknown error"
            state["status"].config(text="Status: failed")
            self._set_text(state["results"], f"{label} failed:\n{err}")
            self._log(f"ERROR: {label} failed: {err}")
            return

        text, status = formatter(result["data"])
        self._set_text(state["results"], text + f"\n\nSaved: {result['out_path']}")
        state["status"].config(text=f"Status: {status}")
        self._log_slow(f"{label}: {status}.")

    # --- Flight Logs ---

    def _handle_flight_logs(self):
        def fn(manifest_path):
            from forensics.analysis import analyze_flight_logs
            return analyze_flight_logs(manifest_path)
        self._run_analysis(self.fl_card, "Flight-log parse", fn,
                           "flight_logs.json", self._fmt_flight_logs)

    def _fmt_flight_logs(self, data):
        n = data.get("log_count", 0)
        lines = [f"Flight logs: {n}", ""]
        for it in data.get("items", []):
            lines.append(f"[{it.get('file_type')}] {it.get('relative_path')} "
                         f"({it.get('size_bytes')}b)")
            st = it.get("status")
            if st == "parsed":
                lines.append(f"   lines: {it.get('line_count')}  "
                             f"{it.get('format_guess', '')}")
                for pl in it.get("preview", [])[:5]:
                    lines.append(f"   | {pl}")
            elif st == "binary":
                lines.append(f"   binary .DAT  header: {it.get('header_hex', '')[:32]}...")
                lines.append(f"   {it.get('note', '')}")
            else:
                lines.append(f"   status: {st}")
            lines.append("")
        return "\n".join(lines), f"{n} log(s) parsed"

    # --- Media Metadata ---

    def _handle_media_metadata(self):
        def fn(manifest_path):
            from forensics.analysis import analyze_media
            return analyze_media(manifest_path)
        self._run_analysis(self.mm_card, "Media metadata", fn,
                           "media_metadata.json", self._fmt_media)

    def _fmt_media(self, data):
        n = data.get("media_count", 0)
        lines = [f"Media files: {n}", ""]
        for it in data.get("items", []):
            lines.append(f"[{it.get('file_type')}] {it.get('relative_path')} "
                         f"({it.get('size_bytes')}b)")
            if it.get("exif_available"):
                cam = f"{it.get('camera_make', '')} {it.get('camera_model', '')}".strip()
                lines.append(f"   {it.get('format', '?')} {it.get('dimensions', '')}"
                             + (f"  cam: {cam}" if cam else ""))
                if it.get("datetime"):
                    lines.append(f"   taken: {it.get('datetime')}")
                if it.get("gps_present"):
                    lines.append("   GPS: present")
            else:
                lines.append(f"   {it.get('note', 'no EXIF')}")
            lines.append("")
        return "\n".join(lines), f"{n} media file(s) analyzed"

    # --- Steganography ---

    def _handle_steganography(self):
        def fn(manifest_path):
            from forensics.analysis import analyze_stego
            return analyze_stego(manifest_path)
        self._run_analysis(self.steg_card, "Steganography scan", fn,
                           "steganography.json", self._fmt_stego)

    def _fmt_stego(self, data):
        scanned = data.get("images_scanned", 0)
        susp = data.get("suspicious", 0)
        lines = [f"Images scanned: {scanned}   Suspicious: {susp}", ""]
        for fnd in data.get("findings", []):
            lines.append(f"{fnd.get('relative_path')}")
            for fl in fnd.get("flags", []):
                lines.append(f"   - {fl}")
            lines.append("")
        return "\n".join(lines), f"{susp} suspicious / {scanned} scanned"

    # ====================
    # Functions for video
    # ====================

    # =============================
    # Functions for system logging
    # =============================
    
    def _log(self, message):
        """
        Adds an instant message to the queue.
        """

        self.log_queue.put(("fast", message))
    
        return
    
    def _log_slow(self, message, delay=45):
        """
        Logs a message to the terminal output window with a typewriter effect
        """

        self.log_queue.put(("slow", message, delay))

        return

    def _process_log_queue(self):
        """
        Processes messages one by one.
        Waits for previous message to finish before checking for new ones.
        """

        if self.is_logging:
            self.after(20, self._process_log_queue)
            return
        
        try:
            item = self.log_queue.get_nowait()
            mode = item[0]
            message = item[1]

            if mode == "fast":
                self.text_terminal.config(state=tk.NORMAL)
                self.text_terminal.insert(tk.END, f"> {message}\n")
                self.text_terminal.see(tk.END)
                self.text_terminal.config(state=tk.DISABLED)

                #Process next messsage immediately
                self.after(10, self._process_log_queue)

            elif mode == "slow":
                delay = item[2]
                self.is_logging = True # Block queue

                self._type_message_loop(message, delay, 0)

        except queue.Empty:

            # Check frequently
            self.after(100, self._process_log_queue)

    def _type_message_loop(self, message, delay, index):
        """
        Helper function to type characters one by one.
        """
        self.text_terminal.config(state=tk.NORMAL)
        
        # Insert prompt prefix
        if index == 0:
            self.text_terminal.insert(tk.END, "> ")
            self.text_terminal.see(tk.END)

        if index < len(message):
            self.text_terminal.insert(tk.END, message[index])
            self.text_terminal.see(tk.END)
            self.text_terminal.config(state=tk.DISABLED)

            # Schedule next char
            self.after(delay, self._type_message_loop, message, delay, index + 1)
        else:
            # Done typing
            self.text_terminal.insert(tk.END, "\n")
            self.text_terminal.config(state=tk.DISABLED)
            self.is_logging = False
            self._process_log_queue()

    def connection_watcher(self):
        """
        PRODUCTION: Monitors for active Tello Wi-Fi connection.
        Only triggers when Ubuntu confirms it is 'activated' on a TELLO-XXXX network.
        """
        # while True:
        #     try:
        #         # Ask NetworkManager for the name of the currently activated Wi-Fi
        #         cmd = "nmcli -t -f NAME,STATE connection show --active | grep ':activated' | cut -d':' -f1"
        #         output = subprocess.check_output(cmd, shell=True, text=True).strip()
        #         active_networks = output.split('\n')

        #         # Check if any active network contains 'TELLO' in the name
        #         is_on_tello = any("TELLO" in net.upper() for net in active_networks if net)

        #         if is_on_tello and not self.drone_connected:
        #             self.drone_connected = True
        #             self._log_slow("[!] Tello Link Established. Use Flight Deck button to launch controls.")

        #         elif not is_on_tello:
        #             if self.drone_connected:
        #                 self._log("[!] Tello link lost.")
        #             self.drone_connected = False

        #     except Exception:
        #         # nmcli fails if no network is active; we just treat as disconnected
        #         self.drone_connected = False

        #     # Check every 3 seconds to keep it responsive but light on CPU
        #     time.sleep(3)

    def launch_controller(self):
        """Launches the external controkollerGUI.py file"""
        self._handle_open_controller()
