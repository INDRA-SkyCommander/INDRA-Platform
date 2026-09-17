import os
import time
import subprocess
from . import iw_parse
from . import iwlist_parse

cell_info = {}

# Special return codes for scan errors
SCAN_ERROR_UNSUPPORTED_INTERFACE = "SCAN_ERROR_UNSUPPORTED_INTERFACE"
SCAN_ERROR_GENERIC = "SCAN_ERROR_GENERIC"


def _run_iw_scan(interface, timeout=10):
	"""Runs `iw dev <interface> scan` once. Returns stdout on success, None on failure."""
	try:
		result = subprocess.run(
			f"sudo iw dev {interface} scan",
			shell=True,
			capture_output=True,
			text=True,
			timeout=timeout,
			stdin=subprocess.DEVNULL
		)
		if result.returncode == 0 and result.stdout:
			return result.stdout
		error_msg = result.stderr or result.stdout or "Unknown error"
		print(f"[!] iw scan failed: {error_msg[:200]}")
	except subprocess.TimeoutExpired:
		print("[!] iw scan timed out")
	except Exception as e:
		print(f"[!] iw scan error: {e}")
	return None


def _run_iwlist_scan(interface, timeout=10):
	"""Runs `iwlist <interface> scan` once. Returns stdout on success, None on failure."""
	try:
		result = subprocess.run(
			f"sudo iwlist {interface} scan",
			shell=True,
			capture_output=True,
			text=True,
			timeout=timeout,
			stdin=subprocess.DEVNULL
		)
		if result.returncode == 0 and result.stdout:
			return result.stdout
		error_msg = result.stderr or result.stdout or "Unknown error"
		print(f"[!] iwlist scan failed: {error_msg[:200]}")
	except subprocess.TimeoutExpired:
		print("[!] iwlist scan timed out")
	except Exception as e:
		print(f"[!] iwlist scan error: {e}")
	return None


def _reset_interface(interface):
	"""
	Best-effort recovery for a stuck interface: kills anything that might
	be holding it (wpa_supplicant, NetworkManager's wifi agent), makes
	sure it's not rfkill-blocked, and cycles it down/up. Only called as a
	fallback after a direct scan attempt has already failed, not on every
	scan - most scans don't need this.
	"""
	print(f"[*] Resetting interface {interface}...")

	for cmd in (
		"sudo killall -9 wpa_supplicant wpa_cli 2>/dev/null",
		f"sudo nmcli dev disconnect {interface} 2>/dev/null",
		"sudo rfkill unblock wifi",
	):
		try:
			subprocess.run(cmd, shell=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=3)
		except Exception:
			pass

	try:
		subprocess.run(f"sudo ip link set {interface} down", shell=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=3)
		time.sleep(1)
		subprocess.run(f"sudo ip link set {interface} up", shell=True, capture_output=True, stdin=subprocess.DEVNULL, timeout=3)
		time.sleep(1)
	except Exception:
		pass


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

	# `iw` talks to the kernel over nl80211, which is what these adapters
	# actually support, so try it directly first - this is the fast path
	# and succeeds the overwhelming majority of the time.
	parser = iw_parse
	scan_output = _run_iw_scan(interface)

	# Fall back to a full interface reset + retries only if the direct
	# attempt failed, instead of paying that cost on every single scan.
	if not scan_output:
		print("[*] Direct iw scan failed, attempting interface recovery...")
		_reset_interface(interface)

		for attempt in range(2):
			scan_output = _run_iw_scan(interface, timeout=12)
			if scan_output:
				break
			time.sleep(2)

	# Last resort: iwlist (legacy WEXT). Some drivers only implement one
	# of the two APIs, so keep this as a fallback even though iw is
	# preferred.
	if not scan_output:
		print("[*] iw scan unavailable, falling back to iwlist...")
		parser = iwlist_parse
		scan_output = _run_iwlist_scan(interface)
		if not scan_output:
			_reset_interface(interface)
			scan_output = _run_iwlist_scan(interface, timeout=12)

	if not scan_output:
		print(f"[!] Scan failed for interface {interface}: no output from iw or iwlist")
		status_result = subprocess.run(f"ip link show {interface}", shell=True, capture_output=True, text=True)
		print(f"[DEBUG] Interface status:\n{status_result.stdout}")

		with open(raw_output_path, 'w') as f:
			f.write("")

		if "no such device" in status_result.stdout.lower() or "does not exist" in status_result.stderr.lower():
			return SCAN_ERROR_UNSUPPORTED_INTERFACE
		return SCAN_ERROR_GENERIC

	with open(raw_output_path, 'w') as f:
		f.write(scan_output)

	# if new results are blank, don't overwrite previous results with blank results
	if os.stat(raw_output_path).st_size == 0:
		return

	cell_list = parser.get_cells(scan_output)

	#Writes a new file that outputs the names and addresses of the scanned targets
	with open(scan_results_file_path, "w") as f:

		#iterates through each cell in the list
		#each cell contains an list of values outputted by the scan
		for cell in cell_list:

			#if the name of the address has no name, change it to no name
			strname = parser.get_name(cell)
			if strname == "":
				strname = "N/A"

			target_address = parser.get_address(cell)
			target_name = f"{strname} - {target_address}"

			print(f"Adding {target_name} to host list")

			cell_info[target_name] = [parser.get_name(cell), parser.get_address(cell), parser.get_quality(cell), parser.get_channel(cell), parser.get_signal_level(cell), parser.get_encryption(cell)]

			f.write(target_name + "\n")

	return cell_info
