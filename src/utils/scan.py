import os
import time
import subprocess
from .iwlist_parse import *

cell_info = {}

# Special return codes for scan errors
SCAN_ERROR_UNSUPPORTED_INTERFACE = "SCAN_ERROR_UNSUPPORTED_INTERFACE"
SCAN_ERROR_GENERIC = "SCAN_ERROR_GENERIC"

def scan(interface="wlan0"):
	"""
	This method is responsible for going into the OS shell and scanning for networks using the WIFI card. It then outputs the raw data to a file. 
	This data is then parsed into a new file and new information for use in the GUI

	Args:
		interface (str): The network interface to use for scanning. Default is "wlan0".
	
	Returns:
		cell_info: A dictionary which holds all the necessary information of the different hosts.
		The cell_info dictionary has a key with the name of the hosts and the mac address in the format "SSID - <MAC ADDRESS>". The key values are as follows:
		The name of the cell, the MAC address, the quality, the channel, the signal level, and the encryption type. This is used in the GUI later to list the info of every host.
		
		Special return codes:
		SCAN_ERROR_UNSUPPORTED_INTERFACE: The specified interface does not support wireless scanning.
		SCAN_ERROR_GENERIC: A generic error occurred during scanning.
	"""

	cell_list = [[]]
	global cell_info
	cell_info = {}
	
	current_dir = os.path.dirname(__file__)
	data_folder = os.path.join(current_dir, "..", "..", "data")
	os.makedirs(data_folder, exist_ok=True)

	raw_output_path = os.path.join(data_folder, "raw_output.txt")
	scan_results_file_path = os.path.join(data_folder, "scan_results.txt")

	# AGGRESSIVE INTERFACE RESET - Kill all scanning/connection processes
	print(f"[*] Performing aggressive interface reset for {interface}...")
	
	# Kill all competing processes that might lock the interface
	kill_commands = [
		f"sudo killall -9 wpa_cli wpa_supplicant iw iwlist 2>/dev/null",
		f"sudo killall -9 nm-wifi-watcher 2>/dev/null",
		f"sudo killall -9 wpa_supplicant 2>/dev/null",
	]
	for cmd in kill_commands:
		try:
			subprocess.run(cmd, shell=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=2)
		except:
			pass
	time.sleep(1)
	
	# Disconnect from any network
	print(f"[*] Disconnecting from any active networks...")
	try:
		subprocess.run(f"nmcli dev disconnect {interface}", shell=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=3)
	except:
		pass
	time.sleep(0.5)
	
	# Make sure WiFi is not blocked by rfkill
	print(f"[*] Ensuring WiFi is enabled...")
	try:
		subprocess.run(f"sudo rfkill unblock wifi", shell=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=3)
	except:
		pass
	time.sleep(0.5)
	
	# Flush any pending operations on the interface by bringing it down and back up
	print(f"[*] Flushing interface state...")
	try:
		subprocess.run(f"sudo ip link set {interface} down", shell=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=3)
		time.sleep(0.5)
		subprocess.run(f"sudo ip link set {interface} up", shell=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=3)
	except:
		pass
	time.sleep(1)
	
	# Try multiple scanning methods in order of preference
	print(f"[*] Attempting to scan {interface}...")
	
	return_code = -1
	scan_output = ""
	
	# Method 1: iw command (more reliable, handles large result sets better than iwlist)
	print(f"[*] Trying iw scan...")
	max_retries = 5
	
	for attempt in range(max_retries):
		if attempt > 0:
			# Longer delays when device is busy - it needs time to recover
			if attempt == 1:
				delay = 3
				print(f"[!] Device busy, giving interface extra recovery time...")
			elif attempt == 2:
				delay = 5
				print(f"[!] Still busy, performing secondary interface reset...")
				try:
					subprocess.run(f"sudo ip link set {interface} down", shell=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=2)
					time.sleep(1)
					subprocess.run(f"sudo ip link set {interface} up", shell=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=2)
				except:
					pass
			else:
				delay = 6 + (attempt * 2)
			
			print(f"[*] iw attempt {attempt + 1}/{max_retries} (waiting {delay}s)...")
			time.sleep(delay)
		
		try:
			# Use subprocess.run to avoid argument list length issues with os.system
			result = subprocess.run(
				f"sudo iw {interface} scan 2>&1",
				shell=True,
				capture_output=True,
				text=True,
				timeout=12,
				stdin=subprocess.DEVNULL
			)
			if result.returncode == 0 and result.stdout:
				scan_output = result.stdout
				return_code = 0
				print(f"[+] iw scan successful ({len(scan_output)} bytes)")
				break
			else:
				error_msg = result.stderr or result.stdout or "Unknown error"
				print(f"[!] iw attempt {attempt + 1} failed: {error_msg[:100]}")
				if "busy" in error_msg.lower() or "resource temporarily unavailable" in error_msg.lower():
					print(f"[!] Interface busy, retrying with longer delay...")
					continue
		except subprocess.TimeoutExpired:
			print(f"[!] iw scan timed out (attempt {attempt + 1})")
			continue
		except Exception as e:
			print(f"[!] iw scan error (attempt {attempt + 1}): {e}")
			continue
	
	# Method 2: iwlist as fallback
	if return_code != 0:
		print(f"[*] iw failed or returned no results, trying iwlist...")
		for attempt in range(max_retries):
			if attempt > 0:
				# Longer delays for busy interface
				if attempt == 1:
					delay = 3
					print(f"[!] Device busy, giving interface extra recovery time...")
				elif attempt == 2:
					delay = 5
					print(f"[!] Still busy, performing secondary interface reset...")
					try:
						subprocess.run(f"sudo ip link set {interface} down", shell=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=2)
						time.sleep(1)
						subprocess.run(f"sudo ip link set {interface} up", shell=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=2)
					except:
						pass
				else:
					delay = 6 + (attempt * 2)
				
				print(f"[*] iwlist attempt {attempt + 1}/{max_retries} (waiting {delay}s)...")
				time.sleep(delay)
			
			try:
				result = subprocess.run(
					f"sudo iwlist {interface} scan 2>&1",
					shell=True,
					capture_output=True,
					text=True,
					timeout=12,
					stdin=subprocess.DEVNULL
				)
				if result.returncode == 0 and result.stdout:
					scan_output = result.stdout
					return_code = 0
					print(f"[+] iwlist scan successful ({len(scan_output)} bytes)")
					break
				else:
					error_msg = result.stderr or result.stdout or "Unknown error"
					print(f"[!] iwlist attempt {attempt + 1} failed: {error_msg[:100]}")
					if "busy" in error_msg.lower() or "resource temporarily unavailable" in error_msg.lower():
						print(f"[!] Interface busy, retrying with longer delay...")
						continue
			except subprocess.TimeoutExpired:
				print(f"[!] iwlist scan timed out (attempt {attempt + 1})")
				continue
			except Exception as e:
				print(f"[!] iwlist scan error (attempt {attempt + 1}): {e}")
				continue
	
	# Write output to file
	if scan_output:
		with open(raw_output_path, 'w') as f:
			f.write(scan_output)
	
	if return_code != 0:
		# Diagnostic: Check interface status
		print(f"[!] Scan failed. Checking interface status...")
		status_result = subprocess.run(f"ip link show {interface}", shell=True, capture_output=True, text=True)
		print(f"[DEBUG] Interface status:\n{status_result.stdout}")
		
		iw_info = subprocess.run(f"sudo iw {interface} info", shell=True, capture_output=True, text=True)
		print(f"[DEBUG] iw info:\n{iw_info.stdout or iw_info.stderr}")
		
		# Check error output
		if scan_output and "argument list too long" in scan_output.lower():
			print(f"[!] Argument list too long - too many networks in range")
			print(f"[!] Trying with filtered results...")
			# Return error to be handled by caller
			return SCAN_ERROR_GENERIC
		
		if not scan_output:
			print(f"[!] Scan error for interface {interface}: No output from scan tools")
			print(f"[!] This typically means:")
			print(f"    - Interface is not in managed mode")
			print(f"    - Interface is not up")
			print(f"    - WiFi radio is disabled")
			print(f"    - Insufficient permissions")
			return SCAN_ERROR_GENERIC
		else:
			print(f"[!] Scan error for interface {interface}:")
			print(scan_output)
			return SCAN_ERROR_GENERIC

	# if new results are blank, don't overwrite previous results with blank results
	if os.path.exists(raw_output_path):
		file_size = os.stat(raw_output_path).st_size
		
		if file_size == 0:
			with open(raw_output_path, 'w') as f:
				f.write("")
			return
		
	with open(raw_output_path,"r") as f:
		cell_list = get_cells(f.read())

	#Writes a new file that outputs the names and addresses of the scanned targets
	with open(scan_results_file_path, "w") as f:

		#iterates through each cell in the list
		#each cell contains an list of values outputted by the scan
		for cell in cell_list:           
			
			#if the name of the address has no name, change it to no name
			strname = get_name(cell)
			if strname == "":
				strname = "N/A"
				
			target_address = get_address(cell)
			target_name = f"{strname} - {target_address}"

			print(f"Adding {target_name} to host list")

			cell_info[target_name] = [get_name(cell), get_address(cell), get_quality(cell), get_channel(cell), get_signal_level(cell), get_encryption(cell)]
				
			f.write(target_name + "\n")
			
	return cell_info
