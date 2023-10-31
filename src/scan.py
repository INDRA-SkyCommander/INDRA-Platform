import os
import random
from tkinter import END

import GUI
from iwlist_parse import *

cell_info = {}

def scan():
    print("Beep boop. Scanning....")

    GUI.MainGUI.host_list_update = True

    cell_list = [[]]
    
        
    scan_results_file_path=os.path.dirname(__file__) + "/../data/scan_results.txt"
    os.system("iwlist wlan0 scan > ../data/raw_output.txt")

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
            
        return cell_info
#Helper function to mimic a reverse circuit lightswitch, might be moved to GUI.py later
def live_toggle():
    if(GUI.MainGUI.switch):
        GUI.MainGUI.switch = False
    else:
        GUI.MainGUI.switch = True
                

def get_scan_results(root, list_box):
    file_path=os.path.dirname(__file__) + "/../data/scan_results.txt"
    
    results = ""
    
    if GUI.MainGUI.host_list_update == True:
        print("Updating host list...")
        list_box.delete(0, END)
        with open(file_path, "r") as f:        
            for line in f:
                list_box.insert(END, line)
            GUI.MainGUI.host_list_update = False
            
    
    
    root.after(500, lambda: get_scan_results(root, list_box))
    print(results)

    return results