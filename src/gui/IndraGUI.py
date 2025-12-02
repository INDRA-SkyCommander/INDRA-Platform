# Standard Libraries
import os
import io
import sys
import json
import time
import queue
import base64
import threading
import subprocess

# Tkinter
import tkinter as tk
from tkinter import font
import ttkbootstrap as tb
from ttkbootstrap.constants import *

# Video
from PIL import Image, ImageTk

# Custom Modules
from utils import sudo_exec, module_setup, scan

class IndraGUI(tb.Window):
	"""
	The MainGUI class initializes and controls the main graphical user interface
	for the INDRA application. It contains GUI layout definitions, user interface
	event bindings, threading logic for background scans, and coordination with
	backend modules such as `scan`, `exploit`, and `indra_util`.
	"""

	def __init__(self):
		super().__init__(themename="darkly")

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
		self.auto_scan_cooldown = 12
		
		# Top bar variables
		self.selected_interface = tk.StringVar(value="interfaces")
		self.selected_module = tk.StringVar(value="modules")
		self.options_list = ["Restart Network Adapter", "Stop Monitor Mode"]
		self.selected_option = tk.StringVar(value="options")

		# Host list variables
		self.packets = 30
		self.filter_text = tk.StringVar(value="")
		self.selected_target = tk.StringVar(value="No target selected")

		# Video variables
		self.current_video_frame = None
		self.video_queue = queue.Queue()

		# Log variables
		self.log_queue = queue.Queue()
		self.is_logging = False

		# Appearance
		self._setup_styles()

		# Main Layout
		self.grid_rowconfigure(0, weight=0, minsize=50) # Top Bar
		self.grid_rowconfigure(1, weight=1)             # Main Content
		self.grid_columnconfigure(0, weight=1, minsize=350) # Left Column
		self.grid_columnconfigure(1, weight=2)             # Right Column

		# Functional Components
		self._init_top_bar(row=0, col=0)
		self._init_host_list(row=1, col=0)
		self._init_info_video_terminal_panel(row=1, col=1)

		# ======================
		# Setup message logging
		# ======================

		self._process_log_queue()
		self._log_slow("Initializing system log...")

		# =====================
		# Call autoscan thread
		# =====================

		self._log_slow("Initializing autoscan thread...")
		self.auto_scan_thread = threading.Thread(target=self._auto_scan_loop, daemon=True)
		self.auto_scan_thread.start()

		# ===================
		# Call video threads
		# ===================

		self._log_slow("Intializing video compiling thread...")
		self.monitor_thread = threading.Thread(target=self._monitor_sniff_log, daemon=True)
		self.monitor_thread.start()

		self._log_slow("Intializing video player...")
		self.video_playing = True
		self._start_video_player()

		# ==============
		# Start Program
		# ==============

		self._log_slow("Welcome to INDRA.")
		self._log_slow("Systems initialized. Ready for action!")

	def _setup_styles(self):
		"""
		Defines all fonts and styles in one place.
		"""

		self.styles = tb.Style()

		self.label_font = font.Font(family="Consolas", size=10)
		self.monospace_font = font.Font(family="Consolas", size=10)
		self.exploit_font = font.Font(family="Consolas", size=24, weight="bold")

		self.style.configure("Large.Danger.TButton",
					   background="#c00000",
					   foreground="#ffffff",
					   focuscolor="#c00000",
					   font=self.exploit_font,
					   borderwidth=0,
					   padding=(30, 10, 30, 10)
					   )
		self.style.map("Large.Danger.TButton", background=[("active", "#a30000")])

		self.style.configure("Large.Success.TButton",
					   background="#00c000",
					   foreground="#ffffff",
					   focuscolor="#00c000",
					   font=self.exploit_font,
					   borderwidth=0,
					   padding=(30, 10, 30, 10)
					   )
		self.style.map("Large.Success.TButton", background=[("active", "#00a300")])
		

	def _init_top_bar(self, row, col):
		"""
		Creates the top control bar and binds its events.
		"""

		# ==========
		# GUI Setup
		# ==========

		top_bar_frame = tb.Frame(self, style="TFrame")
		top_bar_frame.grid(row=row, column=col, columnspan=2, sticky="nsew", padx=10, pady=(20, 10))

		for i in range(9): top_bar_frame.grid_columnconfigure(i, weight=1)

		# ======================
		# Buttons and Dropdowns
		# ======================

		# Toggle Scan Button
		self.toggle_btn = tb.Button(top_bar_frame,
							   text="Toggle Scan",
							   style='warning-outline',
							   command=self._handle_toggle_scan
							   )

		# Single Scan Button
		self.scan_btn = tb.Button(top_bar_frame,
							 text="Run Scan",
							 bootstyle='warning-outline',
							 command=self._handle_single_scan
							 )

		# Network Interface Dropdown
		self.interface_dropdown = tb.Combobox(top_bar_frame,
									 state="readonly",
									 font=self.label_font,
									 values=self._get_network_interfaces(),
									 textvariable=self.selected_interface,
									 bootstyle="info",
									 )
		self.interface_dropdown.bind("<<ComboboxSelected>>", self._handle_interface_change)

		# Exploit Module Dropdown
		self.exploit_dropdown = tb.Combobox(top_bar_frame,
									state="readonly",
									font=self.label_font,
									values=self._get_exploit_modules(),
									textvariable=self.selected_module,
									bootstyle="danger"
									)
		self.exploit_dropdown.bind("<<ComboboxSelected>>", self._handle_module_change)
		
		# Misc Options button
		self.options_btn = tb.Button(top_bar_frame,
								text="Execute Option",
								bootstyle="info",
								command=self._handle_option_execute
								)
		
		# Misc Options Dropdown
		self.options_dropdown = tb.Combobox(top_bar_frame,
										state="readonly",
										font=self.label_font,
										values=self.options_list,
										textvariable=self.selected_option,
										bootstyle="info"
										)
		self.options_dropdown.bind("<<ComboboxSelected>>", self._handle_option_change)

		# Exploit Button
		self.exploit_btn = tb.Button(top_bar_frame,
								text="EXPLOIT",
								style="Large.Danger.TButton",
								command=self._handle_run_exploit
								)
		# ================
		# Placing widgets
		# ================

		self.toggle_btn.grid(row=0, column=0, padx=5, pady=5)
		self.scan_btn.grid(row=0, column=1, padx=5, pady=5)

		# Col 2 is spacer

		self.interface_dropdown.grid(row=0, column=3, padx=5, pady=5)
		self.exploit_dropdown.grid(row=0, column=4, padx=5, pady=5)
		
		self.options_dropdown.grid(row=0, column=5, padx=2, pady=5)
		self.options_btn.grid(row=0, column=6, padx=2, pady=5)

		# Col 7 is spacer

		self.exploit_btn.grid(row=0, column=8, padx=10, pady=5, sticky="nsw")

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
		
		sudo_exec(f"ifconfig {interface} down")
		sudo_exec(f"iwconfig {interface} mode managed")
		sudo_exec(f"ifconfig {interface} up")

		self._log_slow("Beep boop. Scanning...")

		def _scan_and_exit():
			try:
				self.all_targets = scan(interface)
			except Exception as e:
				self._log(f"Error! aborting scan: {e}")
				return

		t = threading.Thread(target=_scan_and_exit)
		t.start()

		self.scan_btn.configure(text="Run Scan", bootstyle="success-outline", state=NORMAL)
		self.is_scanning = False

		if len(self.all_targets) < 1:
			self._log("Error! Could not find any targets.")
			return
		else:
			self._get_scan_results()
			self._log_slow("Scan successfully completed!")

		return
	
	def _get_scan_results(self):
		"""
		Updates scan results to the GUI and backend.
		"""

		file_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'scan_results.txt')
		try:
			with open(file_path, 'r') as f:
				for line in f:
					self.host_listbox.insert(END, line)
		except FileNotFoundError:
			self._log(f"Scan results not found at {file_path}.")
		
		self._handle_filter_change()

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

		return

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

		return
	
	def _get_target(self):
		"""
		Returns the currently selected target from the host list
		"""

		target = None

		try:
			target = self.host_listbox.get(tk.ACTIVE)
		except Exception:
			self._log("Error retrieving selected target.")
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

		target_data_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "module_input_data.json")

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
				"interface": interface.strip(),
				}
			}
		
		try:
			with open(target_data_path, "w") as f:
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
			finally:
				sudo_exec(f"ifconfig {interface} down")
				sudo_exec(f"iwconfig {interface} mode managed")
				sudo_exec(f"ifconfig {interface} up")

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
	
	def _init_host_list(self, row, col):
		"""
		Creates the host list, filter bar, and binds its events.
		"""

		# ==========
		# GUI Setup
		# ==========

		host_list_frame = tb.Labelframe(self, text="Host List", bootstyle="warning")
		host_list_frame.grid(row=row, column=col, sticky="nsew", padx=10, pady=5)

		# Internal frame for filter box
		filter_bar = tb.Frame(host_list_frame, bootstyle="secondary")
		filter_bar.pack(fill=tk.X, padx=5, pady=(0, 5))

		tb.Label(filter_bar, text="Filter ", bootstyle="warning").pack(side=LEFT)

		# Filter box
		self.filter_entry = tb.Entry(filter_bar,
						   bootstyle="warning",
						   font=self.label_font,
						   textvariable=self.filter_text
						   )
		self.filter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
		self.filter_entry.bind("<KeyRelease>", self._handle_filter_change)
	
		# Frame for Host Listbox
		listbox_frame = tb.Frame(host_list_frame, bootstyle="warning")
		listbox_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=5)

		# Host Listbox
		self.host_listbox = tk.Listbox(listbox_frame,
								 bg="#2e3238",
								 fg="#ffffff",
								 font=self.monospace_font,
								 selectbackground="#20374c",
								 borderwidth=1,
								 relief="flat",
								 highlightthickness=1,
								 highlightbackground="#555555"
								 )
		self.host_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
		self.host_listbox.bind("<<ListboxSelect>>", self._handle_host_selection)

		# Scrollbar for Host Listbox
		scrollbar = tb.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.host_listbox.yview, bootstyle="warning-round")
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

		self.host_listbox.delete(0, END)

		if query.strip() == "":
			for host in self.all_targets:
				self.host_listbox.insert(END, host)
		else:
			for host in self.all_targets:
				if query in host:
					self.host_listbox.insert(END, host)
		
		return

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
		
		self._log(f"Selected target: {self.selected_target.get()}")

		return
	
	def _init_info_video_terminal_panel(self, row, col):
		"""
		Creates the right hand panel with target info, video feed and terminal _log.
		"""

		# ==========
		# GUI Setup
		# ==========

		right_panel_frame = tb.Labelframe(self, text="Information Dashboard", bootstyle="info")
		right_panel_frame.grid(row=row, column=col, sticky="nsew", padx=10, pady=5)

		right_panel_frame.grid_columnconfigure(0, weight=1)
		# Rows: Info (0), Video (1), Terminal (2)
		right_panel_frame.grid_rowconfigure(1, weight=1)
		right_panel_frame.grid_rowconfigure(2, weight=0)

		# Target Info Label
		info_subframe = tb.Frame(right_panel_frame, style="TFrame")
		info_subframe.grid(row=0, column=0, sticky="new", padx=5, pady=5)
		info_subframe.grid_columnconfigure(1, weight=1)
	 	
		self.target_info_label = tb.Label(info_subframe,
										text="Target: No target selected",
										font=self.label_font,
										bootstyle="light",
										justify=tk.LEFT
										)
		self.target_info_label.pack(anchor="w")
		
		# Video Player Frame
		video_frame  = tb.Labelframe(right_panel_frame, text="Live Video Feed", padding=2, bootstyle="info")
		video_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=10)

		# Video Window
		self.video_label = tb.Label(video_frame,
							   text="[ Video Feed Unavailable ]",
							   image=None,
							   font=self.label_font,
							   foreground= "#aaaaaa",
							   anchor="center",
							   bootstyle="secondary-inverse"
							   )
		self.video_label.pack(fill=BOTH, expand=True)

		# Terminal Output Frame
		terminal_frame = tb.Labelframe(right_panel_frame, text="System Log", padding=5, bootstyle="success", height=200)
		terminal_frame.grid(row=2, column=0, sticky="nsew", pady=10)
		terminal_frame.grid_propagate(False)

		# Terminal Window
		self.text_terminal = tk.Text(terminal_frame,
							   wrap=tk.WORD,
							   font=self.monospace_font,
							   bg="#111111",
							   fg="#00ff00",
							   state=tk.DISABLED,
							   relief="flat",
							   borderwidth=0,
							   highlightthickness=0
							   )
		self.text_terminal.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

		# Scrollbar for Terminal Window
		terminal_scrollbar = tb.Scrollbar(terminal_frame, orient=tk.VERTICAL, command=self.text_terminal.yview, bootstyle="success-round")
		terminal_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
		self.text_terminal.config(yscrollcommand=terminal_scrollbar.set)

	# ====================
	# Functions for video
	# ====================

	def _monitor_sniff_log(self):
		"""
		Monitors a log file for video data being written to it.
		Runs in a separate thread.
		"""

		sniff_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "sniff_output.log")
		
		# Make sure file exists, create it if it does not
		if not os.path.exists(sniff_path):
			try:
				os.makedirs(os.path.dirname(sniff_path), exist_ok=True)
				open(sniff_path, 'a').close()
			except Exception as e:
				self._log(f"Error creating sniff output log: {e}")
				return
			
		try:	
			with open(sniff_path, 'r') as f:
				f.seek(0, 2) # Go to EoF

				while True:
					line = f.readline()

					# Handling unable to read line
					if not line:
						time.sleep(0.01)
						continue

					# Valid line, pass to processing
					if line.strip():
						self._process_packet(line.strip())

		except Exception as e:
			self._log(f"Error monitoring log: {e}")
		
		return

	def _process_packet(self, data_packet):
		"""
		Parses data packet from sniffer
		"""

		try:
			# Sanitizing base64 data
			if ":" in data_packet:
				src_ip, clean_packet = data_packet.rsplit(":", 1)
				clean_packet = clean_packet.strip()
			else:
				clean_packet = data_packet.strip()

			if not clean_packet:
				return
			
			# Processing image
			image_bytes = base64.b64decode(clean_packet)
			
			with io.BytesIO(image_bytes) as img_stream:
				img = Image.open(img_stream)

				# Resize image
				img = img.resize((640, 360), Image.Resampling.NEAREST)
				#image_frame = ImageTk.PhotoImage(img)

				# Send to video queue
				self.video_queue.put(img)

		except Exception:
			# Ignore malformed images
			pass

		return

	def _start_video_player(self):
		"""
		Polls the video queue, converts images to ImageTk and updates the GUI.
		"""

		try:
			while not self.video_queue.empty():

				# Get frame from queue without blocking
				frame = self.video_queue.get_nowait()
				tk_frame = ImageTk.PhotoImage(frame)

				# Update GUI
				self.video_label.configure(image=tk_frame, text="")
				self.current_video_frame = tk_frame # Prevent garbage collection

		except queue.Empty:
			pass
		finally:
			if self.video_playing:
				self.after(15, self._start_video_player)
		
		return

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