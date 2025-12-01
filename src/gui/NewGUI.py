# Standard Libraries
import os
import sys
import json
import threading
import subprocess

# Tkinter
import tkinter as tk
from tkinter import ttk
from tkinter import font

# Video
from PIL import Image, ImageTk

# Custom Modules
from utils import sudo_exec, module_setup, colors

class IndraGUI(tk.Tk):
	"""
	The MainGUI class initializes and controls the main graphical user interface
	for the INDRA application. It contains GUI layout definitions, user interface
	event bindings, threading logic for background scans, and coordination with
	backend modules such as `scan`, `exploit`, and `indra_util`.
	"""

	def __init__(self):
		super().__init__()

		# Tkinter Window
		self.title("INDRA")
		self.geometry("1400x850")
		self.resizable(False, False)

		# Data Stuctures
		self.all_targets = []
		self.video_playing = False
		self.video_frame_count = 0

		# Scan variables
		self.scan_toggled = False
		self.is_scanning = False
		
		# Top bar variables
		self.selected_interface = tk.StringVar(value="interfaces")
		self.selected_module = tk.StringVar(value="modules")
		self.options_list = ["", "Restart Network Adapter", "Stop Monitor Mode"]
		self.selected_option = tk.StringVar(value="options")

		# Host list variables
		self.packets = 30
		self.filter_text = tk.StringVar(value="")
		self.selected_target = tk.StringVar(value="No target selected")

		# Appearance
		self._setup_styles()
		self.config(bg=self.background_slate)

		# Main Layout
		self.grid_rowconfigure(0, weight=0, minsize=50) # Top Bar
		self.grid_rowconfigure(1, weight=1)             # Main Content
		self.grid_columnconfigure(0, weight=1, minsize=350) # Left Column
		self.grid_columnconfigure(1, weight=2)             # Right Column

		# Functional Components
		self._init_top_bar(row=0, col=0)
		self._init_host_list(row=1, col=0)
		self._init_info_video_terminal_panel(row=1, col=1)

		self.log("Welcome to INDRA.\nSystems initialized. Ready for action.")

	def _setup_styles(self):
		"""
		Defines all fonts and colors in one place.
		"""

		self.style = ttk.Style(self)
		self.style.theme_use("clam")

		# Colors
		self.background_slate = colors.TKINTER_SLATE
		self.background_dark = colors.BLACK
		self.background_grey = colors.GREY
		self.background_light = colors.LIGHT_GREY
		self.video_bg = colors.TKINTER_SLATE
		self.text_color = colors.WHITE
		self.accent_orange = colors.ORANGE
		self.accent_red = colors.RED
		self.accent_green = colors.GREEN
		self.accent_blue = colors.BLUE

		# Font styles
		self.header_font = font.Font(family="Consolas", size=16, weight="bold")
		self.button_font = font.Font(family="Consolas", size=10, weight="bold")
		self.label_font = font.Font(family="Consolas", size=10)
		self.monospace_font = font.Font(family="Consolas", size=10)
		self.exploit_font = font.Font(family="Consolas", size=24, weight="bold")

		# Widget styles
		self.style.configure("Tframe", background=self.background_dark)
		self.style.configure("TLabel", background=self.background_dark, foreground=self.text_color)
		self.style.configure("Tcombobox", background=self.background_light, foreground=self.text_color, fieldbackground=self.background_light)
		self.style.configure("TLabelframe", background=self.background_dark, bordercolor=self.background_grey, relief="solid", borderwidth=4)
		self.style.configure("TLabelframe.Label", background=self.background_dark, foreground=self.text_color, font=self.header_font)
		self.style.configure("Filter.TEntry", background=self.background_light, foreground=self.text_color, fieldbackground=self.background_light)
		self.style.configure("TFilter", background=self.background_grey, foreground=self.text_color, font=self.label_font)

		# Button styles
		self.style.configure("Orange.TButton", background=self.accent_orange, foreground=self.text_color, font=self.button_font, padding=[10, 5], relief="flat")
		self.style.map("Orange.TButton", background=[('active', self.accent_orange)])
		self.style.configure("Red.TButton", background=self.accent_red, foreground=self.text_color, font=self.button_font, padding=[10, 5], relief="flat")
		self.style.map("Red.TButton", background=[('active', self.accent_red)])
		self.style.configure("Green.TButton", background=self.accent_green, foreground=self.text_color, font=self.button_font, padding=[10, 5], relief="flat")
		self.style.map("Green.TButton", background=[('active', self.accent_green)])
		self.style.configure("Blue.TButton", background=self.accent_blue, foreground=self.text_color, font=self.button_font, padding=[10, 5], relief="flat")
		self.style.map("Blue.TButton", background=[('active', self.accent_blue)])
		self.style.configure("Exploit.TButton", background=self.accent_orange, foreground=self.text_color, font=self.exploit_font, padding=[4, 4], relief="flat")
		self.style.map("Exploit.TButton", background=[('active', self.accent_orange)])

	def _init_top_bar(self, row, col):
		"""
		Creates the top control bar and binds its events.
		"""

		# ==========
		# GUI Setup
		# ==========

		top_bar_frame = ttk.Frame(self, style="TFrame")
		top_bar_frame.grid(row=row, column=col, columnspan=2, sticky="nsew", padx=10, pady=(10, 5))

		for i in range(9): top_bar_frame.grid_columnconfigure(i, weight=0 if i in [2, 6] else 1)

		# ======================
		# Buttons and Dropdowns
		# ======================

		# Toggle Scan Button
		self.toggle_btn = ttk.Button(top_bar_frame,
							   text="Toggle Scan", 
							   style="Orange.TButton", 
							   command=self._handle_toggle_scan
							   )

		# Single Scan Button
		self.scan_btn = ttk.Button(top_bar_frame,
							 text="Scan Once",
							 style="Orange.TButton",
							 command=self._handle_single_scan
							 )

		# Network Interface Dropdown
		self.interface_dropdown = ttk.Combobox(top_bar_frame,
									 state="readonly",
									 font=self.label_font,
									 values=self._get_network_interfaces(),
									 textvariable=self.selected_interface
									 )
		self.interface_dropdown.bind("<<ComboboxSelected>>", self._handle_interface_change)

		# Exploit Module Dropdown
		self.exploit_dropdown = ttk.Combobox(top_bar_frame,
									state="readonly",
									font=self.label_font,
									values=self._get_exploit_modules(),
									textvariable=self.selected_module
									)
		self.exploit_dropdown.bind("<<ComboboxSelected>>", self._handle_module_change)

		# Exploit Button
		self.exploit_btn = ttk.Button(top_bar_frame,
								text="EXPLOIT",
								style="Exploit.TButton",
								command=self._handle_run_exploit
								)
		
		# Misc Options button
		self.options_btn = ttk.Button(top_bar_frame,
								text="Execute Option",
								style="Orange.TButton",
								command=self._handle_option_execute
								)
		
		# Misc Options Dropdown
		self.options_dropdown = ttk.Combobox(top_bar_frame,
										state="readonly",
										font=self.label_font,
										values=self.options_list
										)
		self.options_dropdown.bind("<<ComboboxSelected>>", self._handle_option_change)

		# ================
		# Placing widgets
		# ================

		self.toggle_btn.grid(row=0, column=0, padx=0, pady=5, sticky="w")
		self.scan_btn.grid(row=0, column=1, padx=5, pady=20, sticky="w")

		# Col 2 is spacer

		self.interface_dropdown.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
		self.exploit_dropdown.grid(row=0, column=4, padx=5, pady=5, sticky="ew")
		self.exploit_btn.grid(row=0, column=5, padx=5, pady=20, sticky="ew")

		# Col 6 is spacer

		self.options_dropdown.grid(row=0, column=7, padx=5, pady=5, sticky="e")
		self.options_btn.grid(row=0, column=8, padx=5, pady=5, sticky="e")

	# ======================
	# Functions for top bar
	# ======================

	def _handle_toggle_scan(self):
		"""
		Handles the scan toggling logic.

		Actual toggle value is sensed by the auto-scanning thread.
		"""

		self.scan_toggled = not self.scan_toggled

		self.log(f"Toggle scan state: {self.scan_toggled}")

		if self.scan_toggled:
			self.toggle_btn.config(text="Stop Scanning")
			self.toggle_btn.config(style="Red.TButton")
		else:
			self.toggle_btn.config(text="Start Scanning")
			self.toggle_btn.config(style="Green.TButton")
	
	def _handle_single_scan(self):
		"""
		Handles a single scan event.
		"""

		# Call reference to scan here
		self.log("Performing single scan...")

		return
	
	def _get_network_interfaces(self):
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

	def _get_exploit_modules(self):
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
	
	def _get_target(self):
		"""
		Returns the currently selected target from the host list
		"""

		target = None

		try:
			target = self.host_listbox.get(tk.ACTIVE)
		except Exception:
			self.log("Error retrieving selected target.")
			return None
		
		return target
	
	def _get_target_info(self, target_name):
		"""
		Returns the target info list for the given target name.
		"""

		if target_name.strip() in self.all_targets:
			return self.all_targets[target_name.strip()]
		else:
			return None

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
			self.log("Please stop scanning before running an exploit.")
			return -1

		target_name = self._get_target()
		if target_name is None:
			self.log("Please select target first.")
			return -1
		
		exploit = self._get_module()
		if exploit is None:
			self.log("Please select exploit module first.")
			return -1

		interface = self._get_interface()
		if interface is None:
			self.log("Please select network interface first.")
			return -1
		
		target_info = self._get_target_info(target_name)
		if target_info is None:
			self.log("Error retrieving target info.")
			return -1

		target_data_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "target_data.json")

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
				"mac_address": target_info[1].strip() if len(target_info) > 1 else "",
				"quality": target_info[2].strip() if len(target_info) > 2 else "",
				"channel": target_info[3].strip() if len(target_info) > 3 else "",
				"signal_level": target_info[4].strip() if len(target_info) > 4 else "",
				"encryption": target_info[5].strip() if len(target_info) > 5 else ""
				},
				
			"options": {
				"packets": self.packets,
				"interface": interface.strip() if interface else "",
				}
			}
		
		try:
			with open(target_data_path, "w") as f:
				json.dump(target_data, f, indent=4)
		except Exception as e:
			self.log(f"Error writing to JSON file: {e}")
			return -1

		exploit_path = os.path.join(os.path.dirname(__file__), "..", "..", "modules", f"{exploit}", f"{exploit}.py")
		src_path = os.path.join(os.path.dirname(__file__), "..", "..", "src")
		env = os.environ.copy()
		env["PYTHONPATH"] = f"{src_path}{os.pathsep}{env.get('PYTHONPATH', '')}"

		self.log(f"Launching exploit: {exploit} on target: {target_name}")

		try: 
			module_return_code = subprocess.call([sys.executable, exploit_path], env=env)
			self.log(f"Module {exploit} finished with return code: {module_return_code}")
		except Exception as e:
			self.log(f"Error executing module {exploit}: {e}")
			return -1
		finally:
			sudo_exec(f"ifconfig {interface} down")
			sudo_exec(f"iwconfig {interface} mode managed")
			sudo_exec(f"ifconfig {interface} up")

			return module_return_code

	def _handle_option_execute(self):
		"""
		Executes the selected misc option from the dropdown.
		"""

		match self.selected_option:
			case "Restart Network Adapter":
				self.log("Restarting Network Adapter...")
				sudo_exec("service NetworkManager restart")
			case "Stop Monitor Mode":
				if self.selected_interface.get() == "interfaces":
					self.log("Please select a network interface first.")
				else:
					self.log("Stopping Monitor Mode...")
					sudo_exec(f"airmon-ng stop {self.selected_interface.get()}")
			case _:
				self.log("No option selected or unrecognized option.")

	def _handle_option_change(self, event=None):
		"""
		Updates the selected option when changed from the dropdown.
		"""
		
		selected = self.options_dropdown.get()
		self.selected_option = selected

	def _init_host_list(self, row, col):
		"""
		Creates the host list, filter bar, and binds its events.
		"""

		# ==========
		# GUI Setup
		# ==========

		host_list_frame = ttk.Labelframe(self, text="Host List", style="TLabelframe")
		host_list_frame.grid(row=row, column=col, sticky="nsew", padx=10, pady=5)

		# Internal frame for filter box
		filter_bar = ttk.Frame(host_list_frame, style="TFrame")
		filter_bar.pack(fill=tk.X, padx=5, pady=(0, 5))

		ttk.Label(filter_bar, text="Filter: ", style="TLabel").pack(side=tk.LEFT, padx=(0, 10))

		# Filter box
		self.filter_entry = ttk.Entry(filter_bar,
						   style="Filter.TEntry",
						   font=self.label_font,
						   textvariable=self.filter_text
						   )
		self.filter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
		self.filter_entry.bind("<KeyRelease>", self._handle_filter_change)
	
		# Frame for Host Listbox
		listbox_frame = ttk.Frame(host_list_frame, style="TFrame")
		listbox_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

		# Host Listbox
		self.host_listbox = tk.Listbox(listbox_frame,
								 bg=self.background_grey,
								 fg=self.text_color,
								 font=self.monospace_font,
								 selectbackground=self.accent_blue,
								 borderwidth=2,
								 relief="solid"
								 )
		self.host_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
		self.host_listbox.bind("<<ListboxSelect>>", self._handle_host_selection)

		# Scrollbar for Host Listbox
		scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.host_listbox.yview)
		scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
		self.host_listbox.config(yscrollcommand=scrollbar.set)

	# ========================
	# Functions for host list
	# ========================

	def _handle_filter_change(self, event=None):
		"""
		Updates the host list based on the filter text.
		"""

		query = self.filter_text.get()
		self.host_listbox.delete(0, tk.END)

		for host in self.all_targets:
			if query in host:
				self.host_listbox.insert(tk.END, host)

	def _handle_host_selection(self, event=None):
		"""
		Updates the UI when a host is selected from the listbox.
		"""

		try:
			selection = self.host_listbox.get(self.host_listbox.curselection())
			if not selection:
				self.selected_target.set("No target selected")
				return
			selected = self.host_listbox.get(selection[0])
			self.selected_target.set(selected)
		except Exception:
			self.selected_target.set("No target selected")
			return
		
		self.log(f"Selected target: {self.selected_target.get()}")
	
	def _init_info_video_terminal_panel(self, row, col):
		"""
		Creates the right hand panel with target info, video feed and terminal log.
		"""

		# ==========
		# GUI Setup
		# ==========

		right_panel_frame = ttk.LabelFrame(self, text="Information Dashboard", style="TLabelframe")
		right_panel_frame.grid(row=row, column=col, sticky="nsew", padx=10, pady=5)

		right_panel_frame.grid_columnconfigure(0, weight=1)
		# Rows: Info (0), Video (1), Terminal (2)
		right_panel_frame.grid_rowconfigure(1, weight=1)
		right_panel_frame.grid_rowconfigure(2, weight=1)

		# Target Info Label
		info_subframe = ttk.Frame(right_panel_frame, style="TFrame")
		info_subframe.grid(row=0, column=0, sticky="new", padx=5, pady=5)
		info_subframe.grid_columnconfigure(1, weight=1)
	 	
		self.target_info_label = ttk.Label(info_subframe,
										text="Target: No target selected",
										font=self.label_font,
										background=self.background_dark,
										foreground=self.text_color,
										anchor="w",
										justify=tk.LEFT
										)
		self.target_info_label.grid(row=0, column=0, sticky="w", padx=5, pady=5)
		
		# Video Player Frame
		video_frame  = ttk.LabelFrame(right_panel_frame, text="Live Video Feed")
		video_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=10)
		self.video_label = ttk.Label(video_frame, text="Video Feed Unavailable", font=self.label_font, background=self.video_bg, foreground=self.background_grey, anchor="center")
		self.video_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

		# Terminal Output Frame
		terminal_frame = ttk.LabelFrame(right_panel_frame, text="Terminal Output", style="TLabelframe")
		terminal_frame.grid(row=2, column=0, sticky="nsew", padx=5, pady=10)

		# Terminal Window
		self.text_terminal = tk.Text(terminal_frame,
							   wrap=tk.WORD,
							   font=self.monospace_font,
							   bg=self.background_grey,
							   fg=self.text_color,
							   state=tk.DISABLED,
							   relief="flat")
		self.text_terminal.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

		# Scrollbar for Terminal Window
		terminal_scrollbar = ttk.Scrollbar(terminal_frame, orient=tk.VERTICAL, command=self.text_terminal.yview)
		terminal_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
		self.text_terminal.config(yscrollcommand=terminal_scrollbar.set)

	# ====================================
	# Functions for info, video, terminal
	# ====================================

	def log(self, message):
		"""
		Logs a message to the terminal output window.
		"""

		self.text_terminal.config(state=tk.NORMAL)
		self.text_terminal.insert(tk.END, f"{message}\n")
		self.text_terminal.see(tk.END)
		self.text_terminal.config(state=tk.DISABLED)

	def video_play(self):
		"""
		Handles video playback in the video feed area.
		"""

		if not self.video_playing:
			return

		# Video playback logic here

		return