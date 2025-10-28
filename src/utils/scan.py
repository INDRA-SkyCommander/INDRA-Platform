import os
from tkinter import END
from .iwlist_parse import *

cell_info = {}

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
    """

    print("Beep boop. Scanning...")

    cell_list = [[]]
    global cell_info
    
    current_dir = os.path.dirname(__file__)
    data_folder = os.path.join(current_dir, "..", "..", "data")
    os.makedirs(data_folder, exist_ok=True)

    raw_output_path = os.path.join(data_folder, "raw_output.txt")
    scan_results_file_path = os.path.join(data_folder, "scan_results.txt")

    # run scan
    os.system(f'iwlist {interface} scan > {raw_output_path}')
    
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

            print(f"Adding {target_name} to dictionary")

            cell_info[target_name] = [get_name(cell), get_address(cell), get_quality(cell), get_channel(cell), get_signal_level(cell), get_encryption(cell)]

            for item in cell_info[target_name]:
                print(item)
                
            f.write(target_name + "\n")
            
        return cell_info

# def get_scan_results(root, list_box):
#     """
#     This method is responsible for updating the list of hosts on the GUI itself.

#     Args: 
#         root: root window
#         list_box: A list on the GUI that is meant for displaying the scanned hosts

#     Returns
#         results (str): Returns a list of hosts from the scan results file, which contains the SSID and MAC address of every available host

#     """
#     file_path=os.path.dirname(__file__) + "/../data/scan_results.txt"
    
#     results = ""
    
#     if MainGUI.host_list_update == True:
#         list_box.delete(0, END)
#         with open(file_path, "r") as f:        
#             for line in f:
#                 if("TELLO" in line):
#                     list_box.insert(END, line)
#             MainGUI.host_list_update = False
    
#     # prevent console from constantly printing whitespace
#     if results != '':
#         print(results)

#     root.after(1000, lambda: get_scan_results(root, list_box))

#     return results


