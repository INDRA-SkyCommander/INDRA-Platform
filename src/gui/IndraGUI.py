# Standard Libraries
import os
import sys
import json
import time
import queue
import signal
import base64
import threading
import subprocess

# Tkinter
import tkinter as tk
from tkinter import font
import ttkbootstrap as tb
from ttkbootstrap.constants import * # pyright: ignore[reportWildcardImportFromLibrary]

# Video
import av
from PIL import Image, ImageTk


# Custom Modules
from utils import sudo_exec, module_setup
from utils.scan import scan, SCAN_ERROR_UNSUPPORTED_INTERFACE, SCAN_ERROR_GENERIC

class IndraGUI(tb.Window):
	"""
	The IndraGUI class initializes and controls the main graphical user interface
	for the INDRA application. It contains GUI layout definitions, user interface
	event bindings, threading logic for background scans, and coordination with
	backend modules.
	"""

	def __init__(self):
		super().__init__(themename="darkly")

		# Tkinter Window
		self.title("INDRA")
		self.geometry("1400x850")
		self.resizable(False, False)

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

		# Video variables
		self.current_video_frame = None
		self.video_queue = queue.Queue()
		self.codec = av.CodecContext.create('h264', 'r')
		self.video_file_position_reset = False  # Flag to signal file position reset on new exploit
		self.module_running = False
		self.current_module_process = None
		self.current_module_name = None
		self.stop_module_requested = False

		# Log variables
		self.log_queue = queue.Queue()
		self.is_logging = False
		self.fast_log_mode = os.getenv("INDRA_FAST_LOGS", "1") != "0"
		self.default_typewriter_delay = 0 if self.fast_log_mode else 1
		self.typewriter_chunk_size = 6

		# Appearance
		self._setup_styles()

		# Main Layout
		self.grid_rowconfigure(0, weight=0, minsize=50) # Top Bar
		self.grid_rowconfigure(1, weight=1)             # Main Content
		self.grid_columnconfigure(0, weight=1, minsize=350) # Left Column
		self.grid_columnconfigure(1, weight=2)             # Right Column

		# Functional Components
		self._init_top_bar(row=0, col=0, sections=9)
		self._init_host_list(row=1, col=0)
		self._init_info_video_terminal_panel(row=1, col=1)
		self.bind_all("<Control-c>", self._handle_ctrl_c_stop_module)
		self.bind_all("<Control-C>", self._handle_ctrl_c_stop_module)

		# ======================
		# Setup necessary files
		# ======================

		self._setup_files()
		self._log("Setting up necessary directories...")

		# ======================
		# Setup message logging
		# ======================

		self._process_log_queue()
		self._log("Initializing system log...")

		# =====================
		# Call autoscan thread
		# =====================

		self._log("Initializing autoscan thread...")
		self.auto_scan_thread = threading.Thread(target=self._auto_scan_loop, daemon=True)
		self.auto_scan_thread.start()

		# ===================
		# Call video threads
		# ===================

		self._log("Intializing video compiling thread...")
		self.monitor_thread = threading.Thread(target=self._monitor_sniff_log, daemon=True)
		self.monitor_thread.start()

		self._log("Intializing video player...")
		self.video_playing = True
		self._start_video_player()

		# ==============
		# Start Program
		# ==============

		self._log("Welcome to INDRA.")
		self._log("Systems initialized. Ready for action!")

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
		Defines all fonts and styles in one place.
		"""

		self.styles = tb.Style()

		self.label_font = font.Font(family="Consolas", size=11)
		self.monospace_font = font.Font(family="Consolas", size=11)
		self.exploit_font = font.Font(family="Consolas", size=22, weight="bold")

		self.style.configure("Large.Danger.TButton",
					   background="#c00000",
					   foreground="#ffffff",
					   focuscolor="#c00000",
					   font=self.exploit_font,
					   borderwidth=0,
					   padding=(24, 8, 24, 8)
					   )
		self.style.map("Large.Danger.TButton", background=[("active", "#a30000")])

		self.style.configure("Large.Success.TButton",
					   background="#00c000",
					   foreground="#ffffff",
					   focuscolor="#00c000",
					   font=self.exploit_font,
					   borderwidth=0,
					   padding=(24, 8, 24, 8)
					   )
		self.style.map("Large.Success.TButton", background=[("active", "#00a300")])

		self.style.configure("TopBar.TFrame", background="#20262d")
		self.style.configure("MapLike.TLabelframe", borderwidth=1, relief="solid")
		self.style.configure("MapLike.TLabelframe.Label", foreground="#ff5f5f")
		self.style.configure("MapLike.TFrame", background="#1f252c")
		
	def _init_top_bar(self, row: int, col: int, sections: int):
		"""
		Creates the top control bar and binds its events.
		"""

		# ==========
		# GUI Setup
		# ==========

		top_bar_frame = tb.Frame(self, style="TopBar.TFrame")
		top_bar_frame.grid(row=row, column=col, columnspan=2, sticky="nsew", padx=10, pady=(20, 10))

		# Configure columns for even spacing
		# Currently 9 sections
		for i in range(sections): top_bar_frame.grid_columnconfigure(i, weight=1)

		# ======================
		# Buttons and Dropdowns
		# ======================

		# Toggle Scan Button
		self.toggle_btn = tb.Button(top_bar_frame,
							   text="Toggle Scan",
							   style='secondary-outline',
							   command=self._handle_toggle_scan
							   )

		# Single Scan Button
		self.scan_btn = tb.Button(top_bar_frame,
							 text="Run Scan",
						 bootstyle='danger-outline',
							 command=self._handle_single_scan
							 )

		# Network Interface Dropdown
		self.interface_dropdown = tb.Combobox(top_bar_frame,
									 state="readonly",
									 font=self.label_font,
									 values=self._get_network_interfaces(),
									 textvariable=self.selected_interface,
								 bootstyle="danger",
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
							bootstyle="secondary",
								command=self._handle_option_execute
								)
		
		# Misc Options Dropdown
		self.options_dropdown = tb.Combobox(top_bar_frame,
										state="readonly",
										font=self.label_font,
										values=self.options_list,
										textvariable=self.selected_option,
									bootstyle="secondary"
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
		self.interface_dropdown.grid(row=0, column=2, padx=5, pady=5)

		# Col 3 is spacer

		self.options_dropdown.grid(row=0, column=4, padx=5, pady=5)
		self.options_btn.grid(row=0, column=5, padx=5, pady=5)

		# Col 6 is spacer

		self.exploit_dropdown.grid(row=0, column=7, padx=5, pady=5)
		self.exploit_btn.grid(row=0, column=8, padx=10, pady=5, sticky="nsw")

	def _stop_running_module(self):
		if not self.module_running:
			return

		self.stop_module_requested = True
		self._log("Stop requested for running module...")

		proc = self.current_module_process
		if proc and proc.poll() is None:
			try:
				proc.send_signal(signal.SIGINT)
			except Exception as e:
				try:
					proc.terminate()
				except Exception as inner_error:
					self._log(f"Error stopping module process: {inner_error}")

	def _handle_ctrl_c_stop_module(self, _event=None):
		if not self.module_running:
			return None

		module_name = self.current_module_name or "module"
		self._log(f"Ctrl+C received — stopping {module_name}...")
		self._stop_running_module()
		return "break"

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
				scan_result = scan(interface)
				self.is_scanning = False
				self.after(0, lambda: self.scan_btn.configure(text="Run Scan", bootstyle="success-outline", state=NORMAL))

				# Check for special error codes
				if scan_result == SCAN_ERROR_UNSUPPORTED_INTERFACE:
					self._log(f"Error! Interface '{interface}' does not support wireless scanning.")
					return
				elif scan_result == SCAN_ERROR_GENERIC:
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
	
	def _load_module_gui(self, module_name):
		"""
		Dynamically loads and calls a module's GUI if it provides one.

		Looks for  modules/<name>/<name>_gui.py  and calls its
		``prompt_config(parent)`` function, which should return a dict
		of module-specific parameters (or None if the user cancels).

		Returns:
			dict   - config returned by the module GUI
			None   - user cancelled or no GUI file found
			False  - module has no custom GUI (caller should proceed without one)
		"""
		import importlib.util

		gui_path = os.path.join(
			os.path.dirname(__file__), "..", "..",
			"modules", module_name, f"{module_name}_gui.py"
		)
		gui_path = os.path.normpath(gui_path)

		if not os.path.isfile(gui_path):
			return False  # no custom GUI for this module

		try:
			spec = importlib.util.spec_from_file_location(f"{module_name}_gui", gui_path)
			mod = importlib.util.module_from_spec(spec)
			spec.loader.exec_module(mod)
			return mod.prompt_config(self)
		except Exception as e:
			self._log(f"Error loading {module_name} GUI: {e}")
			return None

	def _is_standalone_module(self, module_name):
		"""
		Checks whether a module declares itself as standalone by looking for
		a  STANDALONE = True  flag at the top level of its .py file.

		Standalone modules do not require a wireless target or network interface.

		Uses AST parsing so the module is never executed (no side-effects).
		"""
		import ast

		mod_path = os.path.join(
			os.path.dirname(__file__), "..", "..",
			"modules", module_name, f"{module_name}.py"
		)
		mod_path = os.path.normpath(mod_path)

		if not os.path.isfile(mod_path):
			return False

		try:
			with open(mod_path, "r") as f:
				tree = ast.parse(f.read(), filename=mod_path)

			for node in ast.iter_child_nodes(tree):
				if isinstance(node, ast.Assign):
					for target in node.targets:
						if isinstance(target, ast.Name) and target.id == "STANDALONE":
							if isinstance(node.value, ast.Constant):
								return bool(node.value.value)
			return False
		except Exception:
			return False

	def _handle_run_exploit(self):
		"""
		Executes the selected exploit module against the selected target.
		"""

		if self.module_running:
			self._log("A module is already running. Press Ctrl+C to stop it.")
			return -1

		if self.is_scanning:
			self._log("Please stop scanning before running an exploit.")
			return -1

		exploit = self._get_module()
		if exploit is None:
			self._log("Please select exploit module first.")
			return -1

		is_standalone = self._is_standalone_module(exploit)

		# --- Standalone modules (e.g. gps_spoof): skip target/interface checks ---
		if is_standalone:
			target_data = {}

			module_cfg = self._load_module_gui(exploit)
			if module_cfg is None:
				self._log(f"{exploit} cancelled.")
				return -1
			if module_cfg is not False:
				target_data[exploit] = module_cfg

		else:
			# --- Standard modules: require target + interface ---
			target_name = self._get_target()
			if target_name is None:
				self._log("Please select target first.")
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
			with open(self.json_output_path, "w") as f:
				json.dump(target_data, f, indent=4)
		except Exception as e:
			self._log(f"Error writing to JSON file: {e}")
			return -1

		exploit_path = os.path.join(os.path.dirname(__file__), "..", "..", "modules", f"{exploit}", f"{exploit}.py")
		src_path = os.path.join(os.path.dirname(__file__), "..", "..", "src")
		env = os.environ.copy()
		env["PYTHONPATH"] = f"{src_path}{os.pathsep}{env.get('PYTHONPATH', '')}"

		log_label = f"exploit: {exploit}" if is_standalone else f"exploit: {exploit} on target: {target_name}"
		self._log_slow(f"Launching {log_label}")
		self.module_running = True
		self.stop_module_requested = False
		self.current_module_name = exploit
		self.exploit_btn.config(text="RUNNING", state=tk.DISABLED, style="Large.Success.TButton")

		# Signal video monitor to reset file position for new exploit run
		self.video_file_position_reset = True

		def _run_exploit_thread():
			"""
			Runs the exploit in a background thread so the GUI can continue functioning.
			Streams stdout/stderr to the GUI system log in real time.
			"""

			try:
				proc = subprocess.Popen(
					[sys.executable, "-u", exploit_path],
					env=env,
					stdout=subprocess.PIPE,
					stderr=subprocess.STDOUT,
					bufsize=0,
				)
				self.current_module_process = proc

				if self.stop_module_requested and proc.poll() is None:
					proc.terminate()

				# Read raw bytes so we can detect \r vs \n.
				# Lines using \r (carriage return) are in-place progress
				# updates (e.g. "Time into run = 4.0"). We only log the
				# latest value when a real newline arrives or the stream ends.
				buf = b""
				pending_cr_line = None  # holds the latest \r-only segment

				while True:
					chunk = proc.stdout.read(1)
					if not chunk:
						# Stream ended — flush anything remaining
						if pending_cr_line is not None:
							self._log(pending_cr_line)
							pending_cr_line = None
						remaining = buf.decode("utf-8", errors="replace").strip()
						if remaining:
							self._log(remaining)
						break

					if chunk == b"\n":
						# Real newline — emit the pending \r line if any,
						# then the buffer content.
						if pending_cr_line is not None:
							self._log(pending_cr_line)
							pending_cr_line = None
						text = buf.decode("utf-8", errors="replace").strip()
						if text:
							self._log(text)
						buf = b""

					elif chunk == b"\r":
						# Carriage return — overwrite-style progress update.
						# Just remember the latest value; don't log yet.
						text = buf.decode("utf-8", errors="replace").strip()
						if text:
							pending_cr_line = text
						buf = b""

					else:
						buf += chunk

				proc.wait()
				module_return_code = proc.returncode
				if self.stop_module_requested:
					self._log_slow(f"Module {exploit} stopped.")
				else:
					self._log_slow(f"Module {exploit} finished with return code: {module_return_code}")
			except Exception as e:
				self._log(f"Error executing module {exploit}: {e}")
				return -1
			finally:
				self.current_module_process = None
				self.current_module_name = None
				self.module_running = False
				self.stop_module_requested = False

				# Only reset the network interface for modules that use one
				if not is_standalone:
					interface = self._get_interface()
					if interface:
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

		host_list_frame = tb.Labelframe(self, text="Host List", style="MapLike.TLabelframe", bootstyle="danger")
		host_list_frame.grid(row=row, column=col, sticky="nsew", padx=10, pady=5)

		# Internal frame for filter box
		filter_bar = tb.Frame(host_list_frame, style="MapLike.TFrame")
		filter_bar.pack(fill=tk.X, padx=5, pady=(0, 5))

		tb.Label(filter_bar, text="Filter ", bootstyle="danger").pack(side=LEFT)

		# Filter box
		self.filter_entry = tb.Entry(filter_bar,
						   bootstyle="danger",
						   font=self.label_font,
						   textvariable=self.filter_text
						   )
		self.filter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
		self.filter_entry.bind("<KeyRelease>", self._handle_filter_change)
	
		# Frame for Host Listbox
		listbox_frame = tb.Frame(host_list_frame, style="MapLike.TFrame")
		listbox_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=5)

		# Host Listbox
		self.host_listbox = tk.Listbox(listbox_frame,
								 bg="#1f252c",
								 fg="#dde4ed",
								 font=self.monospace_font,
								 selectbackground="#303b47",
								 selectforeground="#ffffff",
								 borderwidth=1,
								 relief="flat",
								 highlightthickness=1,
								 highlightbackground="#404a55"
								 )
		self.host_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
		self.host_listbox.bind("<<ListboxSelect>>", self._handle_host_selection)

		# Scrollbar for Host Listbox
		scrollbar = tb.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=self.host_listbox.yview, bootstyle="danger-round")
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
	
	def _init_info_video_terminal_panel(self, row, col):
		"""
		Creates the right hand panel with target info, video feed and terminal _log.
		"""

		# ==========
		# GUI Setup
		# ==========

		right_panel_frame = tb.Labelframe(self, text="Information Dashboard", style="MapLike.TLabelframe", bootstyle="danger")
		right_panel_frame.grid(row=row, column=col, sticky="nsew", padx=10, pady=5)

		right_panel_frame.grid_columnconfigure(0, weight=1)
		# Rows: Info (0), Video (1), Terminal (2)
		right_panel_frame.grid_rowconfigure(1, weight=1)
		right_panel_frame.grid_rowconfigure(2, weight=0)

		# Target Info Label
		info_subframe = tb.Frame(right_panel_frame, style="MapLike.TFrame")
		info_subframe.grid(row=0, column=0, sticky="new", padx=5, pady=5)
		info_subframe.grid_columnconfigure(1, weight=1)
	 	
		self.target_info_label = tb.Label(info_subframe,
										text="Target: No target selected",
										font=self.label_font,
										bootstyle="secondary",
										justify=tk.LEFT
										)
		self.target_info_label.pack(anchor="w")
		
		# Video Player Frame
		video_frame  = tb.Labelframe(right_panel_frame, text="Live Video Feed", padding=4, bootstyle="danger")
		video_frame.grid(row=1, column=0, sticky="sew", padx=5, pady=10)

		# Video Window
		self.video_label = tb.Label(video_frame,
							   text="[ Video Feed Unavailable ]",
							   image=None,
							   font=self.label_font,
							   foreground= "#bac5d1",
							   anchor="center",
							   bootstyle="dark"
							   )
		self.video_label.pack(fill=BOTH, expand=True)

		# Terminal Output Frame
		terminal_frame = tb.Labelframe(right_panel_frame, text="System Log", padding=5, bootstyle="danger")
		terminal_frame.grid(row=2, column=0, sticky="sew", pady=10)
		terminal_frame.grid_propagate(False)

		# Terminal Window
		self.text_terminal = tk.Text(terminal_frame,
							   wrap=tk.WORD,
							   font=self.monospace_font,
							   bg="#151b22",
							   fg="#e2e8ef",
							   insertbackground="#ffffff",
							   state=tk.DISABLED,
							   relief="flat",
							   borderwidth=0,
							   highlightthickness=0
							   )
		self.text_terminal.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

		# Scrollbar for Terminal Window
		terminal_scrollbar = tb.Scrollbar(terminal_frame, orient=tk.VERTICAL, command=self.text_terminal.yview, bootstyle="danger-round")
		terminal_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
		self.text_terminal.config(yscrollcommand=terminal_scrollbar.set)

	# ====================
	# Functions for video
	# ====================

	def _get_nal_unit_type(self, data_packet):
		"""
		Extracts NAL unit type from a base64-encoded NAL unit.
		Handles NAL units that include start codes (0x00 0x00 0x00 0x01).
		Returns NAL type (0-31) or None if unable to decode.
		"""
		try:
			# Decode base64 to get raw NAL unit bytes
			nal_bytes = base64.b64decode(data_packet)
			if len(nal_bytes) < 5:  # Minimum: 4-byte start code + 1-byte NAL header
				return None
			
			# Skip past the start code (0x00 0x00 0x00 0x01)
			offset = 0
			if nal_bytes[0:4] == b'\x00\x00\x00\x01':
				offset = 4
			elif nal_bytes[0:3] == b'\x00\x00\x01':
				offset = 3
			
			if offset >= len(nal_bytes):
				return None
			
			# Extract NAL type from first byte after start code (bottom 5 bits)
			nal_header = nal_bytes[offset]
			nal_type = nal_header & 0x1F
			return nal_type
		except Exception:
			return None

	def _monitor_sniff_log(self):
		"""
		Monitors a log file for video data being written to it.
		Reads base64-encoded NAL units and passes them for decoding.
		Handles file position resets when new exploits are launched.
		Runs in a separate thread.
		"""
		
		try:	
			f = None
			frames_processed = 0

			while True:
				# Check if a new exploit run has started - reset file position
				if self.video_file_position_reset:
					if f:
						f.close()
					f = open(self.sniff_output_path, 'r', encoding='utf-8', errors='ignore')
					f.seek(0, 2)  # Go to EOF
					frames_processed = 0
					self.video_file_position_reset = False
					self._log("Video: Restarted file monitoring for new exploit")
					continue
				
				# Open file if not already open
				if f is None:
					f = open(self.sniff_output_path, 'r', encoding='utf-8', errors='ignore')
					f.seek(0, 2)  # Go to EOF

				try:
					line = f.readline()

					# No new data yet, wait and retry
					if not line:
						time.sleep(0.01)
						continue

					# Process this NAL unit
					if line.strip():
						self._process_packet(line.strip())
						frames_processed += 1
						
						# Log progress every 100 NAL units
						if frames_processed % 100 == 0:
							self._log(f"Video: Processed {frames_processed} NAL units")

				except IOError:
					# File may have been moved/deleted, reopen it
					if f:
						f.close()
					f = None
					time.sleep(0.1)
					continue

		except FileNotFoundError:
			self._log("Error: Video log file not found. Sniffer may not have started.")
		except Exception as e:
			self._log(f"Error monitoring video log: {e}")
		finally:
			if f:
				f.close()
		
		return

	def _process_packet(self, data_packet):
		"""
		Decodes H.264 NAL units from base64 and produces video frames.
		The sniffer writes NAL units with start codes, and IDR frames include
		SPS+PPS prepended. PyAV's parse() handles all of this correctly.
		"""

		try:
			# Clean up base64 data (remove any stray whitespace)
			clean_packet = data_packet.strip()
			
			if not clean_packet:
				return
			
			# Skip session separator lines
			if clean_packet.startswith("==="):
				return
			
			# Decode base64 to get raw NAL unit bytes (includes start codes)
			try:
				video_bytes = base64.b64decode(clean_packet)
			except Exception as e:
				self._log(f"Warning: Failed to decode base64 NAL unit: {e}")
				return
			
			# Skip empty packets
			if len(video_bytes) < 5:
				return
			
			# Parse and decode H.264 NAL unit(s) into frames
			# PyAV handles start codes and multiple NAL units (SPS+PPS+IDR) automatically
			try:
				packets = self.codec.parse(video_bytes)
				for packet in packets:
					# Decode each packet into one or more frames
					frames = self.codec.decode(packet)
					for frame in frames:
						try:
							# Convert frame to PIL Image
							img = frame.to_image()
							
							# Resize to fit GUI (640x360 display area)
							img = img.resize((640, 360), Image.Resampling.NEAREST)
							
							# Queue for display on main thread
							self.video_queue.put(img)
						except Exception as e:
							self._log(f"Warning: Failed to convert frame to image: {e}")

			except Exception as e:
				# Only log unexpected errors, not codec state issues
				if "Invalid data" not in str(e):
					self._log(f"Warning: Failed to decode H.264 packet: {e}")
				
		except Exception as e:
			self._log(f"Error processing video packet: {e}")

		return

	def _start_video_player(self):
		"""
		Polls the video queue, converts images to ImageTk and updates the GUI.
		Runs recursively on main thread.
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
	
	def _log_slow(self, message, delay=None):
		"""
		Logs a message to the terminal output window with a typewriter effect
		"""
		if delay is None:
			delay = self.default_typewriter_delay

		if self.fast_log_mode or delay <= 0 or self.log_queue.qsize() > 8:
			self._log(message)
			return

		self.log_queue.put(("slow", message, delay))

		return

	def _process_log_queue(self):
		"""
		Processes messages one by one.
		Waits for previous message to finish before checking for new ones.
		"""

		if self.is_logging:
			self.after(5, self._process_log_queue)
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
				self.after(1, self._process_log_queue)

			elif mode == "slow":
				delay = item[2]
				self.is_logging = True # Block queue

				self._type_message_loop(message, delay, 0)

		except queue.Empty:

			# Check frequently
			self.after(30, self._process_log_queue)

	def _type_message_loop(self, message, delay, index):
		"""
		Helper function to type characters one by one.
		"""
		self.text_terminal.config(state=tk.NORMAL)
		
		# Insert prompt prefix
		if index == 0:
			self.text_terminal.insert(tk.END, "> ")
			self.text_terminal.see(tk.END)

		step = self.typewriter_chunk_size if delay <= 2 else 1
		end_index = min(len(message), index + step)

		if index < len(message):
			self.text_terminal.insert(tk.END, message[index:end_index])
			self.text_terminal.see(tk.END)
			self.text_terminal.config(state=tk.DISABLED)

			# Schedule next char
			self.after(delay, self._type_message_loop, message, delay, end_index)
		else:
			# Done typing
			self.text_terminal.insert(tk.END, "\n")
			self.text_terminal.config(state=tk.DISABLED)
			self.is_logging = False
			self._process_log_queue()