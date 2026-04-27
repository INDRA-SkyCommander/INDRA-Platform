import re

# Original Author
# Hugo Chargois - 17 jan. 2010 - v.0.1
# Parses the output of iwlist scan into a table

# import sys
# import subprocess
# from typing import List, Dict, Optional

interface = "wlan0"


def get_cells(fstring):
	"""
	Parses the output of 'iwlist scan' or 'iw scan' into a table of cells.

	This method takes a string containing the output of either the 'iwlist scan' or 'iw scan' 
	command, which provides information about nearby wireless access points (cells). 
	It extracts and organizes this information into a structured table.

	Args:
		fstring (str): A string containing the output of 'iwlist scan' or 'iw scan'.

	Returns:
		List[List[str]]: A list of lists where each inner list represents the information for a single wireless cell.
		Each inner list contains lines of information related to a specific cell.
	"""

	# Detect format: iw output starts with "BSS" or "phy#", iwlist has "Cell"
	if "BSS" in fstring or ("SSID:" in fstring and "Cell" not in fstring):
		# Parse iw format
		return get_cells_iw(fstring)
	else:
		# Parse iwlist format
		return get_cells_iwlist(fstring)


def get_cells_iwlist(fstring):
	"""Parse iwlist scan output format."""
	cell_list = [[]]

	for line in fstring.split("\n"):
		cell_line = match(line, "Cell ")

		if cell_line != None:
			cell_list.append([])
			line = cell_line[-27:]

		cell_list[-1].append(line.rstrip())

	cell_list = cell_list[1:]
	return cell_list


def get_cells_iw(fstring):
	"""Parse iw scan output format."""
	cell_list = [[]]
	
	for line in fstring.split("\n"):
		# BSS marks the start of a new cell in iw format (e.g., "BSS 34:d2:62:f1:77:56(on wlx9cefd5f66d09)")
		if line.strip().startswith("BSS "):
			cell_list.append([])
			# Extract the MAC address from the BSS line
			# Format: "BSS XX:XX:XX:XX:XX:XX(on interface)"
			bss_line = line.strip()
			# Use regex to extract the MAC address
			mac_match = re.search(r'([0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2})', bss_line)
			if mac_match:
				cell_list[-1].append("Address: " + mac_match.group(1))
		else:
			cell_list[-1].append(line.rstrip())
	
	cell_list = cell_list[1:]
	return cell_list


# You can add or change the functions to parse the properties of each AP (cell)
# below. They take one argument, the bunch of text describing one cell in iwlist
# scan and return a property of that cell.


def get_name(cell):
	"""
	Get the ESSID/SSID from a cell's information.

	This function parses the output of 'iwlist scan' or 'iw scan' for a specific cell 
	and gets the ESSID/SSID, which represents the wireless network name.

	Args:
		cell (str): The information for a wireless network cell obtained from scan output.

	Returns:
		str: The ESSID/SSID (network name) of the wireless network.
	"""
	# Try iwlist format first (ESSID:)
	m = matching_line(cell, "ESSID:")
	if m:
		name = m.strip()
		if len(name) >= 2 and name[0] == '"' and name[-1] == '"':
			name = name[1:-1]
		# Clean up binary/unprintable characters
		name = ''.join(c if c.isprintable() else '' for c in name)
		return name if name else "N/A"
	
	# Try iw format (SSID:)
	m = matching_line(cell, "SSID:")
	if m:
		name = m.strip()
		# Clean up binary/unprintable characters
		name = ''.join(c if c.isprintable() else '' for c in name)
		return name if name else "N/A"
	
	return "N/A"


def get_quality(cell):
	"""
	Parses the quality information from the output of iwlist scan and returns it as a formatted string.

	This method takes a cell, which is a string containing the output of iwlist scan for a specific Wi-Fi network.
	It gets the quality information from the cell, calculates the quality percentage, and returns it as a formatted string.

	Args:
		cell (str): The output of iwlist scan for a specific Wi-Fi network.

	Returns:
		str: A formatted string representing the quality of the Wi-Fi network as a percentage.
	"""
	qline = matching_line(cell, "Quality=")
	if not qline:
		return "N/A"
	
	try:
		parts = qline.split()
		frac = parts[0].split("/")
		numerator = float(frac[0])
		denominator = float(frac[1])
		percent = int(round(numerator / denominator * 100))
		return str(percent).rjust(3) + " %"
	except Exception:
		return "N/A"

def get_channel(cell):
	"""
	Extracts the wireless channel information from a cell's output using iwlist or iw scan.

	This method parses the 'iwlist scan' or 'iw scan' command output for a specific cell 
	and extracts the wireless channel on which the network operates.

	Args:
		cell (str): The output of scan for a specific wireless network cell.

	Returns:
		str: The wireless channel number as a string if found, or 'N/A' if not available.
	"""
	# Try iwlist format (Frequency: with Channel)
	frequency_line = matching_line(cell, "Frequency:")
	if frequency_line:
		if not "Channel" in frequency_line:
			return "N/A"
		else:
			splitchannel = frequency_line.split(" ", 1)
			return splitchannel[1].removeprefix("GHz (Channel").removesuffix(")")
	
	# Try iw format - look for "DS Parameter set: channel X"
	ds_line = matching_line(cell, "DS Parameter set:")
	if ds_line:
		try:
			# Extract channel number from "channel X"
			import re
			match = re.search(r'channel\s+(\d+)', ds_line)
			if match:
				return match.group(1)
		except Exception:
			pass
	
	# Try iw format (primary channel: X)
	channel_line = matching_line(cell, "primary channel:")
	if channel_line:
		try:
			return channel_line.strip().split()[0]
		except Exception:
			return "N/A"
	
	return "N/A"


def get_signal_level(cell):
	"""
	Extracts the signal level from the output of 'iwlist scan' or 'iw scan' for a given wireless cell.

	This function parses the output of 'iwlist scan' or 'iw scan' and extracts the signal level 
	information for a specific wireless cell.

	Parameters:
		cell (str): The string containing the information for the wireless cell.

	Returns:
		str: The signal level of the wireless cell.
	"""
	# Try iwlist format (Signal level on Quality line)
	qline = matching_line(cell, "Quality=")
	if qline and "Signal level" in qline:
		try:
			return qline.split("Signal level=")[1]
		except Exception:
			return "N/A"
	
	# Try iw format (signal: -XX dBm)
	signal_line = matching_line(cell, "signal:")
	if signal_line:
		try:
			return signal_line.strip()
		except Exception:
			return "N/A"
	
	return "N/A"


def get_encryption(cell):
	"""
	Parse the encryption information from the output of iwlist or iw scan.

	This function takes a list of strings (cell) and extracts the encryption information
	to determine the security type of a wireless network.

	Parameters:
		cell (list of str): A list of strings containing the information about a wireless network.

	Returns:
		str: A string representing the encryption type of the wireless network.
	"""
	# Try iwlist format first
	enc = ""
	if matching_line(cell, "Encryption key:") == "off":
		return "Open"
	
	for line in cell:
		matching = match(line, "IE:")
		if matching != None:
			wpa = match(matching, "WPA Version ")
			if wpa != None:
				enc = "WPA v." + wpa
	
	if enc != "":
		return enc
	
	# Try iw format (RSN:, WPA:, or capability)
	# Check for WPA3
	if matching_line(cell, "RSN:"):
		return "WPA3"
	
	# Check for WPA2
	if any("WPA2" in line for line in cell):
		return "WPA2"
	
	# Check for WPA
	if any("WPA" in line and "RSN" not in line for line in cell):
		return "WPA"
	
	# Check for open network (no security)
	if not any("WPA" in line or "RSN" in line for line in cell):
		return "Open"
	
	return "WEP" if enc == "" else enc


def get_address(cell):
	"""
	Extracts the MAC address from a cell's information.

	This function takes a cell object as input and extracts the MAC address
	from the cell's information. The input cell should be in the format
	returned by the 'iwlist scan' or 'iw scan' command.

	Args:
		cell (str): A string containing the information of a wireless network cell.

	Returns:
		str: The MAC address of the wireless network cell in format XX:XX:XX:XX:XX:XX
	"""
	address = matching_line(cell, "Address: ")
	
	if not address:
		return "N/A"
	
	# Extract only the MAC address part (XX:XX:XX:XX:XX:XX format)
	# Some formats might have extra characters after the MAC
	address = address.strip()
	
	# Look for MAC address pattern (6 pairs of hex digits separated by colons)
	mac_match = re.search(r'([0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2})', address)
	
	if mac_match:
		return mac_match.group(1)
	else:
		return address


# Here's a dictionary of rules that will be applied to the description of each
# cell. The key will be the name of the column in the table. The value is a
# function defined above.

rules = {
	"Name": get_name,
	"Quality": get_quality,
	"Channel": get_channel,
	"Encryption": get_encryption,
	"Address": get_address,
	"Signal": get_signal_level,
}

# Here you can choose the way of sorting the table. sortby should be a key of
# the dictionary rules.


def sort_cells(cells):
	"""
	Sort a list of wireless network cells based on a specified attribute.

	This method takes a list of wireless network cells, where each cell is represented
	as a dictionary with various attributes such as SSID, Quality, Signal level, etc.
	It sorts the list of cells based on a specified attribute in descending order (highest to lowest).

	Parameters:
		cells (list): A list of wireless network cells, each represented as a dictionary.
	"""
	sortby = "Quality"
	reverse = True
	cells.sort(None, lambda el: el[sortby], reverse)


# You can choose which columns to display here, and most importantly in what order. Of
# course, they must exist as keys in the dict rules.

columns = ["Name", "Address", "Quality", "Signal", "Channel", "Encryption"]


# Below here goes the boring stuff. You shouldn't have to edit anything below
# this point


def matching_line(lines, keyword):
	"""
	Returns the first matching line in a list of lines.

	This function searches a list of lines for a line that matches a given keyword.
	
	Args:
		lines (list of str): A list of strings, typically lines of text from an iwlist scan.
		keyword (str): The keyword to search for in each line.

	Returns:
		str or None: The first line that contains the specified keyword, or None if no match is found.
	"""
	"""Returns the first matching line in a list of lines. See match()"""
	for line in lines:
		matching = match(line, keyword)
		if matching != None:
			return matching
	return None


def match(line, keyword):
	"""
	Match and extract a substring from a line.

	This function checks if the beginning of the input 'line' (with leading whitespaces stripped)
	matches the provided 'keyword'. If there's a match, it returns the portion of 'line' that comes
	after the 'keyword', effectively extracting that part. If there's no match, it returns None.

	Parameters:
		line (str): The input line to be matched and potentially extracted.
		keyword (str): The keyword to look for at the start of the line.

	Returns:
		str or None: If 'keyword' matches the start of 'line', the function returns the
		substring of 'line' that follows the 'keyword'. If there's no match, it returns None.
	"""
	"""If the first part of line (modulo blanks) matches keyword,
	returns the end of that line. Otherwise returns None"""
	line = line.lstrip()
	length = len(keyword)
	if line[:length] == keyword:
		return line[length:]
	else:
		return None


def parse_cell(cell):
	"""P
	arses the output of 'iwlist scan' into a dictionary, applying rules to the
	input text describing a cell.

	This method takes a text description of a wireless network cell as produced
	by 'iwlist scan' and applies a set of predefined rules to extract relevant
	information into a dictionary. The dictionary will contain key-value pairs
	for attributes such as SSID, signal strength, encryption, etc.

	Parameters:
		cell (str): A text description of a wireless network cell obtained from
			'iwlist scan'.

	Returns:
		dict: A dictionary containing parsed information from the input text.
			The keys represent attributes, and the values are the extracted data.
	"""
	"""Applies the rules to the bunch of text describing a cell and returns the
	corresponding dictionary"""
	parsed_cell = {}
	for key in rules:
		rule = rules[key]
		parsed_cell.update({key: rule(cell)})
	return parsed_cell
