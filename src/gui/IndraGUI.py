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
from tkinter import font, messagebox
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
        # "Segoe UI" / "Consolas" only exist on Windows; on the Ubuntu VM Tk
        # silently substitutes a bitmap font. Use the first family installed.
        installed = {f.lower() for f in font.families()}

        def _pick(*families):
            return next((f for f in families if f.lower() in installed), families[-1])

        sans = _pick("Segoe UI", "Ubuntu", "DejaVu Sans", "Helvetica Neue", "Helvetica")
        mono = _pick("Consolas", "Ubuntu Mono", "DejaVu Sans Mono", "Menlo", "Courier")
        self.title_font     = font.Font(family=sans, size=20, weight="bold")
        self.subtitle_font  = font.Font(family=sans, size=10)
        self.heading_font   = font.Font(family=sans, size=11, weight="bold")
        self.body_font      = font.Font(family=sans, size=10)
        self.label_font     = font.Font(family=mono, size=10)
        self.monospace_font = font.Font(family=mono, size=10)
        self.exploit_font   = font.Font(family=sans, size=12, weight="bold")
        self.table_font     = font.Font(family=sans, size=10)
        self.table_head_font = font.Font(family=sans, size=10, weight="bold")

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

        # ======================
        # Data tables (View CSV)
        # ======================
        # Plain ttk.Treeview never picks up the darkly theme, so its empty area
        # (below / beside the rows) used to render white. Every table uses
        # "Indra.Treeview" so the whole widget is dark.
        self.style.configure("Indra.Treeview",
                             background=c["surface"], fieldbackground=c["surface"],
                             foreground=c["text"], bordercolor=c["border"],
                             lightcolor=c["surface"], darkcolor=c["surface"],
                             borderwidth=0, relief="flat",
                             font=self.table_font, rowheight=26)
        self.style.map("Indra.Treeview",
                       background=[("selected", c["accent_dim"])],
                       foreground=[("selected", "#ffffff")])
        self.style.configure("Indra.Treeview.Heading",
                             background=c["surface_alt"], foreground=c["text"],
                             bordercolor=c["border"], lightcolor=c["surface_alt"],
                             darkcolor=c["surface_alt"], relief="flat",
                             font=self.table_head_font, padding=(6, 6))
        self.style.map("Indra.Treeview.Heading",
                       background=[("active", c["border"])],
                       foreground=[("active", c["text"])])
        # Tooltip shown when hovering a column header.
        self.style.configure("Tooltip.TLabel", background=c["surface_alt"],
                             foreground=c["text"], font=self.body_font,
                             padding=(8, 6), relief="solid", borderwidth=1)

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

        Reads /sys/class/net (always present on Linux, needs no external tools)
        so the dropdown still populates when net-tools/ifconfig isn't installed.
        Falls back to `ip link`, then the legacy ifconfig approach.
        """

        # Primary: /sys/class/net lists every interface, no external command.
        try:
            interfaces = sorted(os.listdir("/sys/class/net"))
            if interfaces:
                return interfaces
        except Exception:
            pass

        # Fallback 1: iproute2 (`ip`), which the rest of the app already uses.
        try:
            output = subprocess.check_output(
                "ip -o link show | awk -F': ' '{print $2}'", shell=True, text=True
            ).strip()
            interfaces = [line.split('@')[0] for line in output.splitlines() if line]
            if interfaces:
                return interfaces
        except Exception:
            pass

        # Fallback 2: legacy net-tools (ifconfig), if it happens to be present.
        try:
            output = subprocess.check_output('ifconfig | cut -d " " -f1', shell=True, text=True).strip()
            return [interface.replace(':', '') for interface in output.splitlines() if interface]
        except Exception:
            return []
    
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
            "Parse extracted DJI flight logs (.TXT, .CSV, .KML, .GPX, .DAT).",
            "Parse Logs", self._handle_flight_logs,
            extra_buttons=[("View CSV", lambda: self._open_csv_viewer(self.fl_card))])
        self.mm_card = self._make_analysis_card(
            grid, 2, 0, "Media Metadata",
            "Extract EXIF / image metadata (camera, timestamp, GPS) from media.",
            "Extract Metadata", self._handle_media_metadata)
        self.steg_card = self._make_analysis_card(
            grid, 2, 1, "Steganography",
            "Scan images for hidden / appended data and embedded file signatures.",
            "Scan Images", self._handle_steganography)

        self.tel_card = self._make_analysis_card(
            grid, 3, 0, "Telemetry — Flight Path Map",
            "Generate a static PNG map of the drone's flight path from extracted CSV logs.",
            "Generate Map", self._handle_telemetry)

        self.sd_card = self._make_analysis_card(
            grid, 3, 1, "SD Card Scan",
            "Quick look, not hashed: copies a card's DJI files, decodes .DAT logs and builds "
            "the media telemetry CSV. Type a drive path (e.g. /media/indra/disk) or an "
            "existing session ID; leave blank to auto-detect the card.",
            "Scan SD Card", self._handle_sd_scan,
            extra_buttons=[("View CSV", lambda: self._open_csv_viewer(
                None, target=self._sd_view_target()))],
            field_label="Drive or session", field_hint="(blank = auto-detect card)")

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
                 text="Evidence copy: copies every file off the card or drive, "
                      "SHA-256 hashes each one and writes a manifest that Integrity "
                      "and Report can verify. Leave the source blank to auto-detect, "
                      "or enter an already-mounted path.",
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

        extracted_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "data", "extracted"))

        if target:
            target = os.path.expanduser(target)
            # Accept a full path, or just a session ID under data/extracted.
            for base in (target, os.path.join(extracted_dir, target)):
                if os.path.isfile(base):
                    return base
                candidate = os.path.join(base, "manifest.json")
                if os.path.isfile(candidate):
                    return candidate
            raise FileNotFoundError(f"No manifest.json found at: {target}")
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

    def _make_analysis_card(self, parent, row, col, title, desc, button_text, command,
                            extra_buttons=(), field_label="Session",
                            field_hint="(blank = most recent)"):
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

        # Pack the buttons first (right-aligned) so they always keep their full
        # width; the entry is packed last and shrinks when the card is narrow.
        # Tk squeezes whatever was packed last, which used to cut "View CSV"
        # down to "View C".
        for extra_text, extra_cmd in reversed(extra_buttons):
            tb.Button(controls, text=extra_text, bootstyle="info-outline",
                      command=extra_cmd).pack(side=tk.RIGHT, padx=(4, 0))
        btn = tb.Button(controls, text=button_text, bootstyle="info", command=command)
        btn.pack(side=tk.RIGHT)
        tb.Label(controls, text=field_hint,
                 style="Muted.TLabel").pack(side=tk.RIGHT, padx=(0, 8))

        tb.Label(controls, text=field_label,
                 style="CardHeading.TLabel").pack(side=tk.LEFT, padx=(0, 6))
        src_var = tk.StringVar(value="")
        entry = tb.Entry(controls, bootstyle="info", font=self.label_font,
                         textvariable=src_var, width=8)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

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
        session_id = os.path.basename(os.path.dirname(result["out_path"] or ""))
        self._set_text(state["results"],
                       f"Session: {session_id}\n\n{text}\n\nSaved: {result['out_path']}")
        status = f"{status} (session {session_id})" if session_id else status
        state["status"].config(text=f"Status: {status}")
        self._log_slow(f"{label}: {status}.")

    # --- Flight Logs ---

    def _handle_flight_logs(self):
        def fn(manifest_path):
            from modules.digital_forensics.analysis import analyze_flight_logs
            return analyze_flight_logs(manifest_path)
        self._run_analysis(self.fl_card, "Flight-log parse", fn,
                           "flight_logs.json", self._fmt_flight_logs)

    def _fmt_flight_logs(self, data):
        items = data.get("items", [])
        logs = [it for it in items if it.get("status") != "skipped"]
        skipped = [it for it in items if it.get("status") == "skipped"]
        media = data.get("media_telemetry") or {}
        n_csv = len(media.get("csv_paths") or [])
        lines = []

        # ---- Real DJI flight logs ----
        lines.append(f"DJI FLIGHT LOGS ({len(logs)})")
        if not logs:
            lines.append("  None in this session. FLY###.DAT logs are stored on the aircraft,")
            lines.append("  DJIFlightRecord .txt logs on the pilot's phone - not on the camera SD card.")
        for it in logs:
            lines.append(f"  {os.path.basename(it.get('relative_path') or '?')}  "
                         f"({it.get('size_bytes')} bytes)")
            st = it.get("status")
            if it.get("csv_path"):
                lines.append(f"    decoded: {it.get('records_parsed')} records -> "
                             f"{os.path.basename(it['csv_path'])}")
            elif "parsed_output" in it:
                for pl in it["parsed_output"].splitlines()[:6]:
                    lines.append(f"    {pl}")
            elif it.get("note"):
                lines.append(f"    {it['note']}")
            if st and st != "parsed":
                lines.append(f"    status: {st}")
        if data.get("output_file"):
            lines.append(f"  Full parser output: {data['output_file']}")
        lines.append("")

        # ---- Media telemetry (the flight data a camera card does have) ----
        lines.append(f"MEDIA TELEMETRY CSV ({n_csv})")
        if n_csv:
            lines.append(f"  {media.get('rows', 0)} GPS points from photos, video headers "
                         f"and MISC/IDX, one CSV per capture session:")
            for g, path in zip(media.get("groups", []), media["csv_paths"]):
                span = g.get("first") or "?"
                if g.get("last") and g.get("last") != g.get("first"):
                    span += f" -> {g['last'][11:] if g['last'][:10] == span[:10] else g['last']}"
                lines.append(f"  {os.path.basename(path)}  ({g.get('rows')} points, {span})")
            lines.append("  Open with View CSV, or Generate Map for the flight-path maps.")
        elif media.get("csv_error"):
            lines.append(f"  Could not build: {media['csv_error']}")
        else:
            lines.append("  No geotagged photos or videos in this session.")
        lines.append("")

        # ---- Files the extractor filed as flight logs that aren't ----
        if skipped:
            lines.append(f"SKIPPED - NOT FLIGHT LOGS ({len(skipped)})")
            lines.append("  Filed under flight_logs/ only because they end in .txt/.dat:")
            for it in skipped:
                name = os.path.basename(it.get("relative_path") or "?")
                lines.append(f"  {name:<20} {it.get('skip_reason', '')}")
                if it.get("preview_line"):
                    lines.append(f"  {'':<20} \"{it['preview_line']}\"")

        status = f"{len(logs)} flight log(s), {n_csv} telemetry CSV(s)"
        if skipped:
            status += f", {len(skipped)} skipped"
        return "\n".join(lines).rstrip(), status

    # --- Decoded .DAT CSV viewer ---

    _CSV_VIEW_MAX_ROWS = 5000

    def _extracted_root(self):
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                            "data", "extracted"))

    def _inside_extracted(self, path):
        root = self._extracted_root()
        path = os.path.abspath(path)
        return path != root and os.path.commonpath([root, path]) == root

    @staticmethod
    def _session_created(path):
        # manifest.json (Acquisition) / report.json (SD Card Scan) are written once
        # when the session is made; the folder's own mtime changes whenever a
        # CSV, map or report is added, so it can't be used.
        for marker in ("manifest.json", "report.json"):
            mp = os.path.join(path, marker)
            if os.path.isfile(mp):
                return os.path.getmtime(mp)
        return os.path.getmtime(path)

    def _sessions_newest_first(self):
        root = self._extracted_root()
        if not os.path.isdir(root):
            return []
        sessions = [os.path.join(root, n) for n in os.listdir(root)
                    if os.path.isdir(os.path.join(root, n))]
        return sorted(sessions, key=self._session_created, reverse=True)

    @staticmethod
    def _has_viewable_data(path):
        for _root, _dirs, files in os.walk(path):
            if any(f.lower().endswith((".csv", ".dat")) for f in files):
                return True
        return False

    def _resolve_session_dir(self, target):
        """
        Session folder from a session ID, a session folder or a file inside it.
        Blank = the most recently *created* session - the same rule every card
        uses, so a blank box always means the same session.
        """
        extracted_dir = self._extracted_root()
        if target:
            target = os.path.expanduser(target)
            # Accept a full path, or just a session ID under data/extracted.
            for path in (os.path.abspath(target), os.path.join(extracted_dir, target)):
                if os.path.isfile(path):
                    return os.path.dirname(path)
                if os.path.isdir(path):
                    return path
            raise FileNotFoundError(f"Session not found: {target}")
        sessions = self._sessions_newest_first()
        if not sessions:
            raise FileNotFoundError(
                "No extractions found yet (data/extracted is empty). "
                "Run an extraction or SD card scan first.")
        return sessions[0]

    def _collect_session_csvs(self, session_dir):
        """
        Decode any .dat in the session that has no <stem>_dat.csv yet, then return
        (csv_paths, notes). Decoded DAT CSVs are listed first.
        """
        dats, csvs = [], []
        for root, _dirs, files in os.walk(session_dir):
            for name in files:
                low = name.lower()
                if low.endswith(".dat"):
                    dats.append(os.path.join(root, name))
                elif low.endswith(".csv"):
                    csvs.append(os.path.join(root, name))

        notes = []
        # Only sessions under data/extracted are ever written to. A drive or any
        # other folder is read-only here, so source media is never modified.
        writable = self._inside_extracted(session_dir)
        if not writable:
            notes.append(f"{session_dir} is outside data/extracted, so nothing was decoded "
                         "or written there. Run an extraction or SD Card Scan first.")
        decoded_stems = {os.path.basename(c)[:-len("_dat.csv")]
                         for c in csvs if c.lower().endswith("_dat.csv")}
        missing = [d for d in dats
                   if os.path.splitext(os.path.basename(d))[0] not in decoded_stems]
        if missing and writable:
            parsing_dir = os.path.abspath(os.path.join(
                os.path.dirname(__file__), "..", "..", "modules",
                "digital_forensics", "parsing"))
            if parsing_dir not in sys.path:
                sys.path.insert(0, parsing_dir)
            from dat_parser import parse_dat

            for dat in missing:
                stem = os.path.splitext(os.path.basename(dat))[0]
                # Next to the .dat first (where telemetry looks); if that folder
                # isn't writable, fall back to the session root.
                res = None
                for out in (os.path.splitext(dat)[0] + "_dat.csv",
                            os.path.join(session_dir, stem + "_dat.csv")):
                    try:
                        res = parse_dat(dat, out)
                        break
                    except PermissionError:
                        continue
                    except Exception as ex:
                        notes.append(f"{os.path.basename(dat)}: decode failed: {ex}")
                        break
                if res is None:
                    if not any(n.startswith(os.path.basename(dat)) for n in notes):
                        notes.append(f"{os.path.basename(dat)}: no writable folder for CSV")
                    continue
                if res.get("csv_path"):
                    csvs.append(out)
                else:
                    notes.append(f"{os.path.basename(dat)}: "
                                 f"{res.get('error') or 'no decodable records'}")

        # Build the media telemetry CSVs (GPS/attitude from photos, videos and
        # MISC/IDX) if this session doesn't have them yet, so View CSV works
        # without running Extract Metadata first.
        manifest_path = os.path.join(session_dir, "manifest.json")
        has_media_csv = any(os.path.basename(c).lower().startswith("media_telemetry_")
                            for c in csvs)
        cache = self.__dict__.setdefault("_media_tel_built", {})
        raw_files = os.path.join(session_dir, "raw_files")   # SD Card Scan layout
        has_source = os.path.isfile(manifest_path) or os.path.isdir(raw_files)
        if not has_media_csv and writable and has_source and session_dir not in cache:
            try:
                from modules.digital_forensics.analysis.media_telemetry import \
                    analyze_media_telemetry, manifest_from_folder
                if os.path.isfile(manifest_path):
                    tel = analyze_media_telemetry(manifest_path)
                else:
                    tel = analyze_media_telemetry(manifest_path, out_dir=session_dir,
                                                  manifest=manifest_from_folder(raw_files))
                csvs.extend(tel.get("csv_paths", []))
                # Remember the result for this run so a session with no geotagged
                # media isn't rescanned on every View CSV click.
                cache[session_dir] = len(tel.get("csv_paths", []))
                if tel.get("csv_error"):
                    notes.append(f"media telemetry CSV: {tel['csv_error']}")
                for sk in tel.get("skipped", []):
                    notes.append(f"skipped {sk.get('file')}: {sk.get('reason')}")
            except Exception as ex:
                notes.append(f"media telemetry CSV failed: {ex}")

        csvs = sorted(set(csvs), key=lambda p: (not p.lower().endswith("_dat.csv"),
                                                os.path.basename(p).lower()))
        return csvs, notes

    def _open_csv_viewer(self, card, target=None):
        if target is None:
            target = card["src_var"].get().strip() if card else ""
        self._log_slow("CSV viewer: locating decoded flight-log CSVs...")

        def _worker():
            result = {"ok": False, "error": None}
            try:
                session_dir = self._resolve_session_dir(target)
                csvs, notes = self._collect_session_csvs(session_dir)
                result.update(ok=True, session_dir=session_dir, csvs=csvs, notes=notes)
                if not csvs and not target:
                    result["alt"] = next((p for p in self._sessions_newest_first()
                                          if p != session_dir and self._has_viewable_data(p)),
                                         None)
            except Exception as e:
                result["error"] = str(e)
            self.after(0, lambda: self._show_csv_viewer(result))

        threading.Thread(target=_worker, daemon=True).start()

    def _show_csv_viewer(self, result):
        if not result["ok"]:
            self._log(f"ERROR: CSV viewer: {result['error']}")
            messagebox.showerror("View CSV", f"Could not open the CSV viewer:\n\n{result['error']}",
                                 parent=self)
            return
        session_dir, csvs, notes = result["session_dir"], result["csvs"], result["notes"]
        for n in notes:
            self._log(f"CSV viewer: {n}")
        if not csvs:
            self._log(f"CSV viewer: no CSVs (or decodable .DAT files) in {session_dir}")
            msg = [f"No CSV could be built for session:\n{os.path.basename(session_dir)}", ""]
            if notes:
                msg += ["Details:"] + [f"  • {n}" for n in notes] + [""]
            msg += [
                "This session has no DJI FLY###.DAT flight log and no geotagged "
                "photos or videos to build a media telemetry CSV from.",
            ]
            alt = result.get("alt")
            if alt:
                msg += ["", f"Open the newest session that has data instead?\n"
                            f"{os.path.basename(alt)}"]
                if messagebox.askyesno("View CSV — nothing to show", "\n".join(msg),
                                       parent=self):
                    self._open_csv_viewer(None, target=alt)
                return
            msg += ["", "To view a different session, type its ID in the Session box first."]
            messagebox.showwarning("View CSV — nothing to show", "\n".join(msg), parent=self)
            return

        import csv as _csv
        import tkinter.font as tkfont
        from tkinter import ttk, filedialog

        parsing_dir = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "..", "modules", "digital_forensics", "parsing"))
        if parsing_dir not in sys.path:
            sys.path.insert(0, parsing_dir)
        from dat_parser import summarize_dat_rows
        import dat_display as dd

        c = self.colors
        win = tb.Toplevel(self)
        win.title(f"Flight Log — {os.path.basename(session_dir)}")
        win.geometry("1200x840")

        # ---- File picker labels: "FLY010.DAT · 757 records" ----
        def _row_count(path):
            try:
                with open(path, "rb") as f:
                    return max(0, sum(1 for _ in f) - 1)
            except OSError:
                return 0

        def _file_label(path):
            name, n = os.path.basename(path), _row_count(path)
            if name.lower().endswith("_dat.csv"):
                return f"{name[:-len('_dat.csv')]}.DAT  ·  {n} records"
            m = re.fullmatch(r"media_telemetry_(.+)\.csv", name, re.I)
            if m:
                return f"Media telemetry {m.group(1)}  ·  {n} point{'s' if n != 1 else ''}"
            return f"{name}  ·  {n} rows"

        labels = [_file_label(p) for p in csvs]
        labels = [f"{lab}  ·  {os.path.basename(os.path.dirname(p))}"
                  if labels.count(lab) > 1 else lab for lab, p in zip(labels, csvs)]
        labels = [f"{lab}  #{i + 1}" if labels.count(lab) > 1 else lab
                  for i, lab in enumerate(labels)]

        # ---- Top bar ----
        bar = tb.Frame(win, padding=(10, 10, 10, 4))
        bar.pack(fill=tk.X)
        tb.Label(bar, text="Flight log", style="CardHeading.TLabel").pack(side=tk.LEFT, padx=(0, 8))
        file_var = tk.StringVar(value=labels[0])
        file_box = tb.Combobox(bar, textvariable=file_var, values=labels,
                               state="readonly", width=42)
        file_box.pack(side=tk.LEFT)

        def _current_path():
            return csvs[labels.index(file_var.get())]

        def _open_folder():
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            try:
                subprocess.Popen([opener, os.path.dirname(_current_path())])
            except Exception as ex:
                self._log(f"ERROR: could not open folder: {ex}")

        tb.Button(bar, text="Open Folder", bootstyle="info-outline",
                  command=_open_folder).pack(side=tk.RIGHT)
        export_btn = tb.Menubutton(bar, text="Export Tab", bootstyle="info-outline")
        export_menu = tk.Menu(export_btn, tearoff=0)
        export_btn["menu"] = export_menu
        export_btn.pack(side=tk.RIGHT, padx=(0, 6))

        path_lbl = tb.Label(win, text="", style="Muted.TLabel", padding=(10, 0))
        path_lbl.pack(fill=tk.X)

        # ---- Flight summary panel ----
        summary = tb.Labelframe(win, text=" Flight Summary ", bootstyle="info", padding=10)
        summary.pack(fill=tk.X, padx=10, pady=(8, 4))

        # ---- Tabs (one per record type, plus Map) + colour legend ----
        legend = tb.Label(win, text=dd.ALERT_LEGEND, style="Muted.TLabel",
                          padding=(10, 0, 10, 8), wraplength=1100, justify=tk.LEFT)
        legend.pack(side=tk.BOTTOM, fill=tk.X)
        tabs = tb.Notebook(win, bootstyle="info")
        tabs.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 6))

        tab_names = {"GPS": "GPS", "FSTAT": "Flight Status", "BATTERY": "Battery",
                     "RC": "RC Sticks", "HOME": "Home Point"}
        tab_order = list(tab_names)
        tab_tables = {}    # notebook tab id -> {"rtype", "cols", "ordered"}
        map_tabs = {}      # notebook tab id -> map state
        current = {"path": None}

        style = ttk.Style()

        def _font(style_name):
            spec = style.lookup(style_name, "font")
            try:
                return tkfont.Font(font=spec) if spec else tkfont.nametofont("TkDefaultFont")
            except tk.TclError:
                return tkfont.nametofont("TkDefaultFont")

        body_font, head_font = _font("Treeview"), _font("Treeview.Heading")

        # ---- Summary ----
        def _fmt_pt(p):
            return f"{p[0]:.6f}, {p[1]:.6f}" if p else "—"

        def _v(x, fmt):
            return "—" if x is None else fmt.format(x)

        def _grid_items(items, warn_keys=()):
            per_col = 4
            for i, (k, val) in enumerate(items):
                r, col = i % per_col, (i // per_col) * 2
                tb.Label(summary, text=k, style="Muted.TLabel").grid(
                    row=r, column=col, sticky="w", padx=(0 if col == 0 else 24, 8), pady=1)
                lbl = tb.Label(summary, text=val, font=self.monospace_font)
                if k in warn_keys:
                    lbl.configure(foreground=c["warning"])
                lbl.grid(row=r, column=col + 1, sticky="w", pady=1)
            return per_col

        def _card_files():
            """Relative paths of every file on the card, for naming-anomaly flags."""
            try:
                with open(os.path.join(session_dir, "manifest.json")) as f:
                    return [e.get("relative_path") or "" for e in json.load(f).get("files", [])]
            except (OSError, ValueError):
                pass
            raw = os.path.join(session_dir, "raw_files")        # SD Card Scan session
            return [os.path.relpath(os.path.join(r, n), raw).replace(os.sep, "/")
                    for r, _d, ns in os.walk(raw) for n in ns] if os.path.isdir(raw) else []

        def _skipped_media():
            try:
                with open(os.path.join(session_dir, "media_telemetry_info.json")) as f:
                    return json.load(f).get("skipped", [])
            except (OSError, ValueError):
                return []

        def _fill_media_summary(rows):
            from modules.digital_forensics.analysis.media_telemetry import summarize_media_rows
            s = summarize_media_rows(rows, _card_files(), _skipped_media())
            src_names = {"photo": "photos", "video": "videos", "idx": "IDX records"}
            sources = ", ".join(f"{n} {src_names.get(k, k)}" for k, n in s["by_source"].items())
            if s["start"]:
                window = s["start"].strftime("%Y-%m-%d %H:%M:%S")
                if s["end"] and s["end"] != s["start"]:
                    window += s["end"].strftime("  →  %H:%M:%S")
            else:
                window = "—"
            length = "—" if s["length_s"] is None else dd.format_duration(s["length_s"])[:-2]
            items = [
                ("Captured",          window),
                ("Time span",         length),
                ("Points",            f"{s['points']} ({sources})"),
                ("Camera",            ", ".join(s["camera_models"]) +
                                      (" (Phantom 4)" if "FC330" in s["camera_models"] else "")
                                      if s["camera_models"] else "—"),
                ("Centre",            _fmt_pt(s["centre"])),
                ("Spread",            _v(s["spread_m"], "{:.0f} m from centre")),
                ("Max altitude MSL",  _v(s["max_abs_alt_m"], "{:.1f} m")),
                ("Max above takeoff", _v(s["max_rel_alt_m"], "{:.1f} m")),
                ("Max speed",         _v(s["max_hspeed_ms"], "{:.1f} m/s")),
                ("Clock",             "camera clock, time zone not recorded"),
                ("Flags",             f"{len(s['flags'])} (listed below)" if s["flags"] else "None"),
            ]
            per_col = _grid_items(items, warn_keys=("Flags",) if s["flags"] else ())
            row = per_col
            tb.Label(summary, style="Muted.TLabel",
                     text="Snapshots taken when each photo was shot or recording started, "
                          "not a continuous flight log.").grid(
                row=row, column=0, columnspan=8, sticky="w", pady=(6, 0))
            for flag in s["flags"]:
                row += 1
                tb.Label(summary, text=f"⚠  {flag}", foreground=c["warning"],
                         font=self.body_font).grid(row=row, column=0, columnspan=8, sticky="w")

        def _fill_summary(rows, is_dat, is_media=False):
            for w in summary.winfo_children():
                w.destroy()
            if is_media:
                _fill_media_summary(rows)
                return
            if not is_dat:
                tb.Label(summary, style="Muted.TLabel",
                         text=f"{len(rows)} rows. Flight summary is available for decoded "
                              f".DAT logs (*_dat.csv).").grid(row=0, column=0, sticky="w")
                return
            s = summarize_dat_rows(rows)
            batt = "—" if s["batt_start_pct"] is None else \
                f"{s['batt_start_pct']:.0f}% → {s['batt_end_pct']:.0f}%"
            sats = "—" if s["sats_min"] is None else (
                str(s["sats_min"]) if s["sats_min"] == s["sats_max"]
                else f"{s['sats_min']}–{s['sats_max']}")
            rc = "—" if s["rc_lost_records"] is None else (
                "Connected throughout" if s["rc_lost_records"] == 0
                else f"Lost in {s['rc_lost_records']} records")
            fails = "—" if s["failure_records"] is None else (
                "None" if s["failure_records"] == 0 else f"{s['failure_records']} records")
            items = [
                ("Flight time",      "—" if s["flight_time_s"] is None
                                     else dd.format_duration(s["flight_time_s"])[:-2]),
                ("Max altitude",     _v(s["max_alt_m"], "{:.1f} m")),
                ("Max speed",        _v(s["max_speed_ms"], "{:.1f} m/s")),
                ("Distance flown",   _v(s["distance_m"], "{:.0f} m")),
                ("Home point",       _fmt_pt(s["home"])),
                ("Max from home",    _v(s["max_from_home_m"], "{:.0f} m")),
                ("Takeoff",          _fmt_pt(s["start"])),
                ("Last position",    _fmt_pt(s["end"])),
                ("Battery",          batt),
                ("Min pack voltage", _v(s["batt_min_v"], "{:.2f} V")),
                ("Max batt temp",    _v(s["batt_max_temp_c"], "{:.0f} °C")),
                ("GPS satellites",   sats),
                ("RC link",          rc),
                ("Failure flags",    fails),
            ]
            per_col = 4
            for i, (k, val) in enumerate(items):
                r, col = i % per_col, (i // per_col) * 2
                tb.Label(summary, text=k, style="Muted.TLabel").grid(
                    row=r, column=col, sticky="w", padx=(0 if col == 0 else 24, 8), pady=1)
                fg = c["danger"] if (k == "RC link" and s["rc_lost_records"]) or \
                    (k == "Failure flags" and s["failure_records"]) else None
                lbl = tb.Label(summary, text=val, font=self.monospace_font)
                if fg:
                    lbl.configure(foreground=fg)
                lbl.grid(row=r, column=col + 1, sticky="w", pady=1)
            modes = " → ".join(dd.FLIGHT_MODES.get(m, f"Code {m}") for m in s["flight_modes"])
            counts = "  ".join(f"{tab_names.get(k, k)} {n}" for k, n in sorted(
                s["counts"].items(),
                key=lambda kv: tab_order.index(kv[0]) if kv[0] in tab_order else 99))
            tb.Label(summary, text=f"Flight modes: {modes or '—'}", style="Muted.TLabel").grid(
                row=per_col, column=0, columnspan=8, sticky="w", pady=(6, 0))
            tb.Label(summary, text=f"Records: {counts}", style="Muted.TLabel").grid(
                row=per_col + 1, column=0, columnspan=8, sticky="w")

        # ---- Header tooltips (one floating label shared by every table) ----
        tip = {"win": None, "key": None}

        def _hide_tip(_e=None):
            if tip["win"] is not None:
                try:
                    tip["win"].destroy()
                except tk.TclError:
                    pass
            tip.update(win=None, key=None)

        def _show_tip(key, text, x_root, y_root):
            if tip["key"] == key:
                return
            _hide_tip()
            tw = tk.Toplevel(win)
            tw.wm_overrideredirect(True)
            tb.Label(tw, text=text, style="Tooltip.TLabel", wraplength=380,
                     justify=tk.LEFT).pack()
            tw.wm_geometry(f"+{x_root + 14}+{y_root + 18}")
            tip.update(win=tw, key=key)

        win.bind("<Destroy>", lambda e: _hide_tip() if e.widget is win else None, add="+")

        # ---- Table tab ----
        # Layout per tab (grid rows): 0 = what this tab is + "show all columns",
        # 1 = table (pinned Time column + the rest), 2 = horizontal scrollbar,
        # 3 = Details panel for the selected row. Small tables (media telemetry,
        # Home Point) are only as tall as their rows; the Details panel gets
        # the rest of the space instead of an empty table.
        def _add_table(title, rtype, cols, rows, friendly, detail_cols=None, raw_cols=None):
            frame = tb.Frame(tabs, padding=(8, 6, 8, 8))
            pinned = [p for p in ("time_s", "timestamp") if friendly and p in cols][:1]
            rest = [col for col in cols if col not in pinned]
            shown = rows[:self._CSV_VIEW_MAX_ROWS]
            iid_rows = {f"r{i}": r for i, r in enumerate(shown)}
            detail_cols = list(detail_cols or cols)
            label_of = {col: (dd.column_label(col) if friendly else col)
                        for col in set(cols) | set(detail_cols)}
            small = len(shown) <= 18

            def cell(col, r):
                return dd.format_value(col, r.get(col)) if friendly else r.get(col, "")

            # Row 0: one line on what this tab is, and the hidden-columns toggle.
            head = tb.Frame(frame)
            head.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
            about = dd.TAB_HELP.get(rtype, "") if friendly else \
                "Columns exactly as they appear in the file."
            hideable = [col for col in rest if friendly and dd.is_uninformative(shown, col)]
            show_all = tk.BooleanVar(value=False)
            if hideable:
                tb.Checkbutton(head, text=f"Show all columns ({len(hideable)} hidden: blank or 0 "
                                          f"in every row)",
                               variable=show_all, bootstyle="info-round-toggle",
                               command=lambda: _apply_columns()).pack(side=tk.RIGHT, padx=(12, 0))
            tb.Label(head, text=about, style="Muted.TLabel", wraplength=760,
                     justify=tk.LEFT).pack(side=tk.LEFT, anchor="w")

            # Row 1-2: the table.
            tree_h = max(1, len(shown)) if small else 16
            trees = []
            if pinned:
                left = ttk.Treeview(frame, show="headings", columns=pinned,
                                    style="Indra.Treeview", height=tree_h)
                left.grid(row=1, column=0, sticky="ns")
                trees.append(left)
            right = ttk.Treeview(frame, show="headings", columns=rest,
                                 style="Indra.Treeview", height=tree_h)
            right.grid(row=1, column=1, sticky="nsew")
            trees.append(right)
            vbar = tb.Scrollbar(frame, orient=tk.VERTICAL)
            vbar.grid(row=1, column=2, sticky="ns")
            hbar = tb.Scrollbar(frame, orient=tk.HORIZONTAL, command=right.xview)
            hbar.grid(row=2, column=1, sticky="ew")
            right.configure(xscrollcommand=hbar.set)
            frame.grid_columnconfigure(1, weight=1)
            frame.grid_rowconfigure(1, weight=0 if small else 3)

            # Keep the pinned and scrolling tables in step (scroll + selection).
            vbar.configure(command=lambda *a: [t.yview(*a) for t in trees])

            def _ysync(src):
                def cmd(first, last):
                    vbar.set(first, last)
                    for t in trees:
                        if t is not src and abs(t.yview()[0] - float(first)) > 1e-9:
                            t.yview_moveto(first)
                return cmd

            def _selsync(src):
                def cb(_e):
                    sel = src.selection()
                    for t in trees:
                        if t is not src and t.selection() != sel:
                            t.selection_set(sel)
                return cb

            def _header_tips(t):
                def motion(e):
                    if t.identify_region(e.x, e.y) != "heading":
                        _hide_tip()
                        return
                    try:
                        idx = int(t.identify_column(e.x).lstrip("#")) - 1
                    except ValueError:
                        return
                    disp = list(t["displaycolumns"])
                    shown_cols = list(t["columns"]) if not disp or disp[0] == "#all" else disp
                    if not 0 <= idx < len(shown_cols):
                        _hide_tip()
                        return
                    col = shown_cols[idx]
                    text = label_of[col]
                    if friendly and dd.column_help(col):
                        text += "\n" + dd.column_help(col)
                    text += "\n(click to sort)"
                    _show_tip((str(t), col), text, e.x_root, e.y_root)
                t.bind("<Motion>", motion, add="+")
                t.bind("<Leave>", _hide_tip, add="+")

            for t in trees:
                t.configure(yscrollcommand=_ysync(t))
                t.bind("<<TreeviewSelect>>", _selsync(t))
                t.tag_configure("even", background=c["surface"])
                t.tag_configure("odd", background=c["surface_alt"])
                t.tag_configure("alert", foreground="#ff7b72")
                t.tag_configure("warn", foreground="#e3b341")
                _header_tips(t)

            sort_state = {"col": None, "desc": False}

            def _zebra(order):
                for idx, iid in enumerate(order):
                    for t in trees:
                        keep = tuple(x for x in t.item(iid, "tags") if x not in ("odd", "even"))
                        t.item(iid, tags=keep + ("odd" if idx % 2 else "even",))

            def _sort(col):
                desc = sort_state["col"] == col and not sort_state["desc"]
                sort_state.update(col=col, desc=desc)

                def key(iid):
                    raw = iid_rows[iid].get(col)
                    num = dd.to_number(raw)
                    return (0, num, "") if num is not None else (1, 0.0, str(raw or ""))

                order = sorted(iid_rows, key=key, reverse=desc)
                for t in trees:
                    for idx, iid in enumerate(order):
                        t.move(iid, "", idx)
                    for cc in t["columns"]:
                        arrow = (" ▼" if desc else " ▲") if cc == col else ""
                        t.heading(cc, text=label_of[cc] + arrow)
                _zebra(order)

            for t in trees:
                for col in t["columns"]:
                    sample = [cell(col, r) for r in shown[:400]]
                    width = max([head_font.measure(label_of[col] + " ▲")] +
                                [body_font.measure(str(v)) for v in sample]) + 32
                    t.heading(col, text=label_of[col], anchor="center",
                              command=lambda col=col: _sort(col))
                    t.column(col, width=max(80, min(360, width)), anchor="center",
                             stretch=False)

            def _apply_columns():
                visible = rest if show_all.get() else [x for x in rest if x not in hideable]
                right["displaycolumns"] = visible or rest

            _apply_columns()

            for idx, (iid, r) in enumerate(iid_rows.items()):
                tags = ("odd" if idx % 2 else "even",)
                level = dd.alert_level(rtype, r) if friendly else None
                if level:
                    tags += (level,)
                for t in trees:
                    t.insert("", tk.END, iid=iid, values=[cell(col, r) for col in t["columns"]],
                             tags=tags)

            # Row 3: Details panel - every field of the selected row, with its meaning.
            details = tb.Labelframe(frame, text=" Details for the selected row ",
                                    bootstyle="secondary", padding=6)
            details.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(10, 0))
            frame.grid_rowconfigure(3, weight=1 if small else 2)
            dcols = ("field", "value", "meaning")
            dtree = ttk.Treeview(details, show="headings", columns=dcols,
                                 style="Indra.Treeview", height=8)
            dv = tb.Scrollbar(details, orient=tk.VERTICAL, command=dtree.yview)
            dh = tb.Scrollbar(details, orient=tk.HORIZONTAL, command=dtree.xview)
            dtree.configure(yscrollcommand=dv.set, xscrollcommand=dh.set)
            dtree.grid(row=0, column=0, sticky="nsew")
            dv.grid(row=0, column=1, sticky="ns")
            dh.grid(row=1, column=0, sticky="ew")
            details.grid_rowconfigure(0, weight=1)
            details.grid_columnconfigure(0, weight=1)
            dtree.tag_configure("even", background=c["surface"])
            dtree.tag_configure("odd", background=c["surface_alt"])
            dtree.tag_configure("blank", foreground=c["text_muted"])
            meanings = [dd.column_help(col) if friendly else "" for col in detail_cols]
            for col_id, text, w in (("field", "Field", 230), ("value", "Value", 300),
                                    ("meaning", "What it means", 0)):
                if col_id == "meaning":
                    w = max([body_font.measure(m) for m in meanings if m] + [300]) + 24
                dtree.heading(col_id, text=text, anchor="w")
                dtree.column(col_id, width=w, anchor="w", stretch=col_id == "meaning")

            def _fill_details(_e=None):
                sel = right.selection()
                if not sel or sel[0] not in iid_rows:
                    return
                r = iid_rows[sel[0]]
                dtree.delete(*dtree.get_children())
                for i, col in enumerate(detail_cols):
                    raw = r.get(col, "")
                    if col == "sha256" or not friendly:
                        val = raw
                    else:
                        val = dd.format_value(col, raw)
                    tags = ("odd" if i % 2 else "even",)
                    if val in (None, ""):
                        val, tags = "— (not recorded)", tags + ("blank",)
                    dtree.insert("", tk.END, values=(label_of.get(col) or dd.column_label(col),
                                                     val, meanings[i]), tags=tags)

            right.bind("<<TreeviewSelect>>", _fill_details, add="+")
            if iid_rows:
                right.selection_set("r0")
                right.focus("r0")
                _fill_details()

            note = f" (first {self._CSV_VIEW_MAX_ROWS})" if len(rows) > len(shown) else ""
            tabs.add(frame, text=f"  {title} ({len(rows)}){note}  ")

            def ordered():
                # Export what's on screen (sorted order); if capped, export every row.
                if len(rows) > len(shown):
                    return rows
                return [iid_rows[i] for i in right.get_children()]

            tab_tables[str(frame)] = {"rtype": rtype, "cols": cols, "ordered": ordered,
                                      "raw_cols": list(raw_cols or cols),
                                      "labels": [dd.export_label(col) if friendly else col
                                                 for col in cols]}

        # ---- Map tab (rendered the first time it's opened) ----
        def _add_map_tab(path, gps_rows):
            if not any(dd.to_number(r.get("latitude")) for r in gps_rows):
                return
            frame = tb.Frame(tabs, padding=10)
            msg = tb.Label(frame, text="Drawing map...", style="Muted.TLabel")
            msg.pack(anchor="w")
            img = tk.Label(frame, background=c["bg"])
            img.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
            tabs.add(frame, text="  Map  ")
            map_tabs[str(frame)] = {"path": path, "msg": msg, "img": img, "started": False}

        def _show_map(state, out, ok):
            if not state["img"].winfo_exists():
                return
            if not ok:
                state["msg"].config(text="Could not draw the map. Install matplotlib "
                                         "for the interpreter the app runs under.")
                return
            try:
                from PIL import Image, ImageTk
                im = Image.open(out)
                im.thumbnail((1120, 560))
                photo = ImageTk.PhotoImage(im)
            except Exception as ex:
                state["msg"].config(text=f"Could not display map: {ex}")
                return
            state["img"].configure(image=photo)
            state["img"].image = photo
            state["msg"].config(text=f"Saved: {out}")

        def _on_tab_changed(_e=None):
            state = map_tabs.get(tabs.select())
            if not state or state["started"]:
                return
            state["started"] = True
            stem = os.path.splitext(os.path.basename(state["path"]))[0]
            # Always redraw (offline, about a second) so an older-style map saved
            # by a previous version is never shown.
            out = os.path.join(session_dir, f"{stem}_flight_map.png")

            def _worker():
                try:
                    from modules.digital_forensics.analysis.telemetry import render_flight_map
                    ok = render_flight_map(state["path"], out)
                except Exception:
                    ok = False
                self.after(0, lambda: _show_map(state, out, ok))

            threading.Thread(target=_worker, daemon=True).start()

        tabs.bind("<<NotebookTabChanged>>", _on_tab_changed)

        # ---- Export current tab ----
        # Saved under data/exports/<session>/ with an "export_" name, so an export
        # can never be mistaken for (or deleted with) a generated media_telemetry_*
        # or *_dat.csv file. Two formats:
        #   readable - on-screen headers, raw values, UTF-8 BOM for Excel
        #   raw      - the original column names (incl. rec_type / source_type),
        #              so the file re-opens in View CSV with the same tabs and summary
        def _export(fmt):
            info = tab_tables.get(tabs.select())
            if not info:
                messagebox.showinfo("Export", "Switch to a table tab first; the Map tab "
                                    "can't be exported as CSV.", parent=win)
                return
            stem = os.path.splitext(os.path.basename(current["path"]))[0]
            suffix = (info["rtype"] or "rows").lower()
            exports_dir = os.path.abspath(os.path.join(
                os.path.dirname(__file__), "..", "..", "data", "exports",
                os.path.basename(session_dir)))
            try:
                os.makedirs(exports_dir, exist_ok=True)
            except OSError:
                exports_dir = os.path.expanduser("~")
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            dest = filedialog.asksaveasfilename(
                parent=win, title=f"Export {suffix} table ({fmt})", initialdir=exports_dir,
                initialfile=f"export_{stem}_{suffix}_{fmt}_{stamp}.csv",
                defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
            if not dest:
                return
            out_rows = info["ordered"]()
            try:
                if fmt == "raw":
                    with open(dest, "w", newline="", encoding="utf-8") as f:
                        w = _csv.DictWriter(f, fieldnames=info["raw_cols"], extrasaction="ignore")
                        w.writeheader()
                        w.writerows(out_rows)
                else:
                    with open(dest, "w", newline="", encoding="utf-8-sig") as f:
                        w = _csv.writer(f)
                        w.writerow(info["labels"])
                        w.writerows([[r.get(col, "") for col in info["cols"]] for r in out_rows])
            except OSError as ex:
                messagebox.showerror("Export failed", str(ex), parent=win)
                return
            self._log_slow(f"Exported {len(out_rows)} rows ({fmt}) to {dest}")

        export_menu.add_command(label="Readable CSV (for Excel)",
                                command=lambda: _export("readable"))
        export_menu.add_command(label="Raw CSV (re-opens in View CSV)",
                                command=lambda: _export("raw"))

        # ---- Load a file ----
        def _load(_event=None):
            path = _current_path()
            current["path"] = path
            path_lbl.config(text=path)
            try:
                with open(path, newline="", encoding="utf-8", errors="replace") as f:
                    reader = _csv.DictReader(f)
                    header = list(reader.fieldnames or [])
                    rows = list(reader)
            except Exception as ex:
                self._log(f"ERROR: could not read {path}: {ex}")
                header, rows = [], []

            for t in tabs.tabs():
                tabs.forget(t)
                win.nametowidget(t).destroy()
            tab_tables.clear()
            map_tabs.clear()

            is_dat = "rec_type" in header
            is_media = not is_dat and {"source_type", "timestamp", "latitude"} <= set(header)
            _fill_summary(rows, is_dat, is_media)
            legend.config(text=dd.ALERT_LEGEND if is_dat else "")   # alerts are DAT-only

            if is_media:
                # Readable headers/values; hide columns that are empty in this file.
                cols = [col for col in header
                        if any(r.get(col) not in (None, "") for r in rows)]
                _add_table("Media Telemetry", "MEDIA", cols, rows, friendly=True,
                           detail_cols=header, raw_cols=header)
                _add_map_tab(path, rows)
                return

            if not is_dat:
                _add_table("All rows", None, header, rows, friendly=False, raw_cols=header)
                _add_map_tab(path, rows)
                return

            by_type = {}
            for r in rows:
                by_type.setdefault(r.get("rec_type") or "UNKNOWN", []).append(r)
            ordered_types = [t for t in tab_order if t in by_type] + \
                sorted(t for t in by_type if t not in tab_order)
            for rtype in ordered_types:
                type_rows = by_type[rtype]
                # Only the columns this record type fills; raw clock tick goes last.
                cols = [col for col in header if col not in ("rec_type", "tick")
                        and any(r.get(col) not in (None, "") for r in type_rows)]
                if "tick" in header:
                    cols.append("tick")
                _add_table(tab_names.get(rtype, rtype), rtype, cols, type_rows, friendly=True,
                           raw_cols=header)
            _add_map_tab(path, by_type.get("GPS", []))

        file_box.bind("<<ComboboxSelected>>", _load)
        _load()
        self._log_slow(f"CSV viewer: {len(csvs)} CSV(s) in {session_dir}")

    # --- Media Metadata ---

    def _handle_media_metadata(self):
        def fn(manifest_path):
            from modules.digital_forensics.analysis import (analyze_media,
                                                            analyze_media_telemetry)
            data = analyze_media(manifest_path)
            # Also build media_telemetry_<date>.csv (GPS/attitude snapshots from
            # photos, videos and MISC/IDX) for View CSV and Generate Map.
            try:
                data["telemetry"] = analyze_media_telemetry(manifest_path)
            except Exception as ex:
                data["telemetry"] = {"csv_paths": [], "csv_error": str(ex)}
            return data
        self._run_analysis(self.mm_card, "Media metadata", fn,
                           "media_metadata.json", self._fmt_media)

    def _fmt_media(self, data):
        n = data.get("media_count", 0)
        gps_hits = 0
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
                # Decoded GPS: real coordinates + a clickable Google Maps link
                if it.get("gps_lat") is not None and it.get("gps_lon") is not None:
                    gps_hits += 1
                    alt = it.get("gps_altitude_m")
                    lines.append(f"   GPS: {it.get('gps_lat')}, {it.get('gps_lon')}"
                                 + (f"  alt {alt}m" if alt is not None else ""))
                    if it.get("gps_maps_url"):
                        lines.append(f"   map: {it.get('gps_maps_url')}")
                elif it.get("gps_present"):
                    lines.append("   GPS: present (coordinates not decodable)")
            else:
                lines.append(f"   {it.get('note', 'no EXIF')}")
            lines.append("")
        status = f"{n} media analyzed"
        if gps_hits:
            status += f", {gps_hits} geotagged"

        tel = data.get("telemetry")
        if tel is not None:
            if tel.get("csv_paths"):
                lines.append(f"Media telemetry CSV: {tel.get('rows', 0)} points "
                             f"({tel.get('with_gps', 0)} with GPS) from photos, videos "
                             f"and MISC/IDX, split by capture session:")
                for g, path in zip(tel.get("groups", []), tel["csv_paths"]):
                    lines.append(f"  {os.path.basename(path)}  ({g['rows']} points, "
                                 f"{g['first']} → {g['last']})")
                lines.append("  Open with View CSV (Flight Logs card) or Generate Map.")
                status += f", {len(tel['csv_paths'])} telemetry CSV(s)"
            elif tel.get("csv_error"):
                lines.append(f"Media telemetry CSV failed: {tel['csv_error']}")
            else:
                lines.append("Media telemetry CSV: no GPS/attitude data found in media.")
        return "\n".join(lines), status

    # --- Steganography ---

    def _handle_steganography(self):
        def fn(manifest_path):
            from modules.digital_forensics.analysis import analyze_stego
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

    # --- Telemetry ---

    def _handle_telemetry(self):
        def fn(manifest_path):
            from modules.digital_forensics.analysis import analyze_telemetry
            return analyze_telemetry(manifest_path)
        self._run_analysis(self.tel_card, "Flight path map", fn,
                           "telemetry.json", self._fmt_telemetry)

    def _fmt_telemetry(self, data):
        n = data.get("maps_generated", 0)
        lines = [f"Maps generated: {n}", ""]
        for it in data.get("items", []):
            lines.append(f"[{it.get('file_type')}] {it.get('relative_path')} "
                         f"({it.get('size_bytes')}b)")
            if it.get("map_path"):
                lines.append(f"   Map saved: {it.get('map_path')}")
            else:
                lines.append(f"   {it.get('note', 'no map generated')}")
            lines.append("")
        return "\n".join(lines), f"{n} map(s) generated"

    # --- SD Card Scan ---

    def _classify_sd_input(self, value):
        """
        What the SD Card Scan box holds: ("drive", path) for an existing folder
        outside data/extracted (a mounted card), ("session", dir) for a session
        ID or session folder, ("auto", None) when blank. Raises ValueError.
        """
        if not value:
            return "auto", None
        path = os.path.abspath(os.path.expanduser(value))
        if os.path.isdir(path) and not self._inside_extracted(path) \
                and path != self._extracted_root():
            return "drive", path
        try:
            return "session", self._resolve_session_dir(value)
        except FileNotFoundError:
            raise ValueError(
                f"\"{value}\" is not a folder on this computer and not a session ID in "
                "data/extracted.\n\nType the card's mount path (e.g. /media/indra/disk), "
                "an existing session ID, or leave the box blank to auto-detect.")

    def _sd_view_target(self):
        """View CSV on the SD card opens the session typed there, else the last scan."""
        value = self.sd_card["src_var"].get().strip()
        try:
            mode, target = self._classify_sd_input(value)
        except ValueError:
            mode, target = None, None
        if mode == "session":
            return target
        return getattr(self, "_last_sd_scan_dir", None) or ""

    def _pick_drive(self, drives):
        """Modal chooser when more than one removable drive is attached."""
        dlg = tb.Toplevel(self)
        dlg.title("Choose a drive")
        dlg.transient(self)
        tb.Label(dlg, text="More than one removable drive is attached. Which one should be "
                           "scanned?", wraplength=380, justify=tk.LEFT).pack(
            anchor="w", padx=16, pady=(16, 8))
        choice = tk.StringVar(value=drives[0])
        for d in drives:
            tb.Radiobutton(dlg, text=d, value=d, variable=choice,
                           bootstyle="info").pack(anchor="w", padx=24, pady=2)
        picked = {"drive": None}
        row = tb.Frame(dlg)
        row.pack(pady=16)
        tb.Button(row, text="Scan", bootstyle="info",
                  command=lambda: (picked.update(drive=choice.get()), dlg.destroy())
                  ).pack(side=tk.LEFT, padx=4)
        tb.Button(row, text="Cancel", bootstyle="secondary",
                  command=dlg.destroy).pack(side=tk.LEFT, padx=4)
        dlg.grab_set()
        self.wait_window(dlg)
        return picked["drive"]

    def _handle_sd_scan(self):
        if self.sd_card["running"]:
            self._log("SD card scan already in progress.")
            return

        _df = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "..", "modules", "digital_forensics")
        for _p in (os.path.join(_df, "telemetry"), os.path.join(_df, "parsing")):
            if _p not in sys.path:
                sys.path.append(_p)
        from scanner import get_usb_drives, scan_drive

        value = self.sd_card["src_var"].get().strip()
        try:
            mode, target = self._classify_sd_input(value)
        except ValueError as ex:
            messagebox.showerror("SD Card Scan", str(ex), parent=self)
            return

        if mode == "auto":
            drives = get_usb_drives()
            if not drives:
                messagebox.showerror(
                    "SD Card Scan",
                    "No removable drives found. Insert the SD card, or type its mount path "
                    "or an existing session ID in the box, and try again.", parent=self)
                return
            target = drives[0] if len(drives) == 1 else self._pick_drive(drives)
            if not target:
                return
            mode = "drive"

        self.sd_card["running"] = True
        self.sd_card["btn"].config(state=tk.DISABLED)
        self.sd_card["status"].config(text="Status: scanning...")
        self._set_text(self.sd_card["results"], "Scanning...")
        if mode == "session":
            self._log_slow(f"Processing session: {os.path.basename(target)}")
        else:
            self._log_slow(f"Scanning drive: {target}")

        def _worker():
            result = {"ok": False, "summary": None, "error": None}
            try:
                if mode == "session":
                    # Existing session: decode any .DAT and build the media telemetry
                    # CSVs in place (only ever inside data/extracted).
                    csvs, notes = self._collect_session_csvs(target)
                    result.update(ok=True, session_mode=True, session_dir=target,
                                  csvs=csvs, notes=notes)
                else:
                    summary = scan_drive(target, self._extracted_root(), log=self._log)
                    result["ok"]      = True
                    result["summary"] = summary
            except Exception as e:
                result["error"] = str(e)

            self.after(0, lambda: self._finish_sd_scan(result))

        threading.Thread(target=_worker, daemon=True).start()

    def _finish_sd_scan(self, result):
        self.sd_card["running"] = False
        self.sd_card["btn"].config(state=tk.NORMAL)

        if not result["ok"]:
            err = result["error"] or "unknown error"
            self.sd_card["status"].config(text="Status: failed")
            self._set_text(self.sd_card["results"], f"Scan failed:\n{err}")
            self._log(f"ERROR: SD card scan failed: {err}")
            return

        if result.get("session_mode"):
            session_dir, csvs = result["session_dir"], result["csvs"]
            self._last_sd_scan_dir = session_dir
            lines = [f"Session : {os.path.basename(session_dir)}",
                     f"CSVs    : {len(csvs)}", ""]
            lines += [f"  {os.path.relpath(c, session_dir)}" for c in csvs]
            if result["notes"]:
                lines += ["", "Notes:"] + [f"  {n}" for n in result["notes"]]
            lines += ["", "Click View CSV to open them." if csvs
                      else "Nothing to view in this session."]
            self._set_text(self.sd_card["results"], "\n".join(lines))
            self.sd_card["status"].config(
                text=f"Status: processed session {os.path.basename(session_dir)} — "
                     f"{len(csvs)} CSV(s)")
            self._log_slow(f"Session processed: {len(csvs)} CSV(s) in {session_dir}")
            return

        summary  = result["summary"] or {}
        total    = sum(len(v) for v in summary.get("files_found", {}).values())
        out_dir  = summary.get("output_dir") or "(none — nothing found)"
        if summary.get("output_dir"):
            self._last_sd_scan_dir = summary["output_dir"]

        lines = [
            f"Drive      : {summary.get('source_drive', '?')}",
            f"Output     : {out_dir}",
            f"Files found: {total}",
            "",
        ]
        for ext, names in summary.get("files_found", {}).items():
            if names:
                lines.append(f"  .{ext}: {len(names)} file(s)")

        extracted = summary.get("extracted", {})
        if extracted:
            lines += ["", "Processed:"]
            for key, val in extracted.items():
                count = len(val) if isinstance(val, list) else "done"
                lines.append(f"  {key}: {count}")

        self._set_text(self.sd_card["results"], "\n".join(lines))
        self.sd_card["status"].config(
            text=f"Status: scanned drive {summary.get('source_drive', '?')} — {total} files")
        self._log_slow(f"SD card scan complete: {total} files. Output: {out_dir}")

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
