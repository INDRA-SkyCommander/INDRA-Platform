# Original Author
# Hugo Chargois - 17 jan. 2010 - v.0.1
# Parses the output of iwlist scan into a table

import sys
import subprocess

interface = "wlan0"


def get_cells(fstring):
    """
    Parses the output of 'iwlist scan' into a table of cells.

    This method takes a string containing the output of the 'iwlist scan' command, which provides information about
    nearby wireless access points (cells). It extracts and organizes this information into a structured table.

    Args:
        fstring (str): A string containing the output of 'iwlist scan'.

    Returns:
        List[List[str]]: A list of lists where each inner list represents the information for a single wireless cell.
        Each inner list contains lines of information related to a specific cell, such as its signal strength, SSID,
        encryption type, etc.
    """

    cell_list = [[]]

    for line in fstring.split("\n"):
        cell_line = match(line, "Cell ")

        if cell_line != None:
            cell_list.append([])

            line = cell_line[-27:]

        cell_list[-1].append(line.rstrip())

    cell_list = cell_list[1:]

    return cell_list


# You can add or change the functions to parse the properties of each AP (cell)
# below. They take one argument, the bunch of text describing one cell in iwlist
# scan and return a property of that cell.


def get_name(cell):
    """
    Get the ESSID (Extended Service Set Identifier) from a cell's information.

    This function parses the output of 'iwlist scan' for a specific cell and gets
    the ESSID, which represents the wireless network name.

    Args:
        cell (str): The information for a wireless network cell obtained from 'iwlist scan'.

    Returns:
        str: The ESSID (network name) of the wireless network.
    """
    return matching_line(cell, "ESSID:")[1:-1]


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
    quality = matching_line(cell, "Quality=").split()[0].split("/")
    return str(int(round(float(quality[0]) / float(quality[1]) * 100))).rjust(3) + " %"


def get_channel(cell):
    """
    Extracts the wireless channel information from a cell's output using iwlist scan.

    This method parses the 'iwlist scan' command output for a specific cell and extracts the wireless channel
    on which the network operates. It searches for the 'Frequency:' line and extracts the channel number
    associated with it.

    Args:
        cell (str): The output of 'iwlist scan' for a specific wireless network cell.

    Returns:
        str: The wireless channel number as a string if found, or 'N/A' if not available in the provided cell data.

    """
    # the channel is a bit more tricky to get since it is next to Frequency, which we don't care about.
    # so we first must take the line and split it by the spaces, but only once
    # then we ONLY want the channel number, so we remove everything around it, and then return
    channelfinal = ""
    frequency_line = matching_line(cell, "Frequency:")

    # we have to first check if there is a channel at all, because some devices don't have one
    if not "Channel" in frequency_line:
        channelfinal = "N/A"
    else:
        splitchannel = frequency_line.split(" ", 1)
        channelfinal = splitchannel[1].removeprefix("GHz (Channel").removesuffix(")")
    return channelfinal


def get_signal_level(cell):
    """
    Extracts the signal level from the output of 'iwlist scan' for a given wireless cell.

    This function parses the output of 'iwlist scan' and extracts the signal level information for a specific wireless cell.
    Signal level data is found on the same line as the 'Quality' data, and this function extracts it using string manipulation.

    Parameters:
        cell (str): The string containing the information for the wireless cell.

    Returns:
        str: The signal level of the wireless cell.
    """
    # Signal level is on same line as Quality data so a bit of ugly
    # hacking needed...
    return matching_line(cell, "Quality=").split("Signal level=")[1]


def get_encryption(cell):
    """
    Parse the encryption information from the output of iwlist scan.

    This function takes a list of strings (cell) and extracts the encryption information
    to determine the security type of a wireless network.

    Parameters:
        cell (list of str): A list of strings containing the information about a wireless network.

    Returns:
        str: A string representing the encryption type of the wireless network. Possible values
        are "Open" for open networks, "WPA v.X" for WPA-protected networks (with X being the version),
        and "WEP" for WEP-protected networks.
    """

    enc = ""
    if matching_line(cell, "Encryption key:") == "off":
        enc = "Open"
    else:
        for line in cell:
            matching = match(line, "IE:")
            if matching != None:
                wpa = match(matching, "WPA Version ")
                if wpa != None:
                    enc = "WPA v." + wpa
        if enc == "":
            enc = "WEP"
    return enc


def get_address(cell):
    """
    Extracts the MAC address from a cell's information.

    This function takes a cell object as input and extracts the MAC address
    from the cell's information. The input cell should be in the format
    returned by the 'iwlist scan' command.

    Args:
        cell (str): A string containing the information of a wireless network cell.

    Returns:
        str: The MAC address of the wireless network cell.
    """
    return matching_line(cell, "Address: ")


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
