import os
import random
from tkinter import END

import GUI
from iwlist_parse import *

cell_info = {}

def scan():
    """
    This method is responsible for going into the OS shell and scanning for networks using the WIFI card. It then outputs the raw data to a file. 
    This data is then parsed into a new file and new information for use in the GUI

    Args:
        None
    
    Returns:
        cell_info: A dictionary which holds all the necessary information of the different hosts.
        The cell_info dictionary has a key with the name of the hosts and the mac address in the format "SSID - <MAC ADDRESS>". The key values are as follows:
        The name of the cell, the MAC address, the quality, the channel, the signal level, and the encryption type. This is used in the GUI later to list the info of every host.
    """

    print("Beep boop. Scanning...")

    os.system("iwlist wlan0 scan > data/raw_output.txt")

    GUI.MainGUI.host_list_update = True

    cell_list = [[]]
    
    scan_results_file_path=os.path.dirname(__file__) + "/../data/scan_results.txt"

    raw_file_path=os.path.dirname(__file__) + "/../data/raw_output.txt"

    with open(raw_file_path,"r") as f:
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
                
            target_name = strname + " - " + target_address
            
            
            print(f"Adding {target_name} to dictionary")
            
            cell_info[target_name] = [get_name(cell), get_address(cell), get_quality(cell), get_channel(cell), get_signal_level(cell), get_encryption(cell)]
            
            for item in cell_info[target_name]:
                print(item)
            
            #Write the contents to the file, which is read by the GUI
            f.write(target_name)
            f.write("\n")
        
        GUI.MainGUI.scanning = False
        
        return cell_info

def get_scan_results(root, list_box):
    """
    This method is responsible for updating the list of hosts on the GUI itself.

    Args: 
        root: root window
        list_box: A list on the GUI that is meant for displaying the scanned hosts

    Returns
        results (str): Returns a list of hosts from the scan results file, which contains the SSID and MAC address of every available host

    """
    file_path=os.path.dirname(__file__) + "/../data/scan_results.txt"
    
    results = ""
    
    if GUI.MainGUI.host_list_update == True:
        list_box.delete(0, END)
        with open(file_path, "r") as f:        
            for line in f:
                list_box.insert(END, line)
            GUI.MainGUI.host_list_update = False
    

    # prevent console from constantly printing whitespace
    if results != '':
        print(results)

    root.after(1000, lambda: get_scan_results(root, list_box))

    return results
