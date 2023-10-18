import os
import random
from tkinter import END

import GUI
from iwlist_parse import *

def scan():
    print("Beep boop. Scanning....")

    GUI.MainGUI.host_list_update = True

    cell_list = [[]]
        
    file_path=os.path.dirname(__file__) + "/../data/scan_results.txt"
    os.system("iwlist wlan0 scan > ../data/raw_output.txt")

    scan_file_path=os.path.dirname(__file__) + "/../data/raw_output.txt"

    with open(scan_file_path,"r") as f:
       cell_list = get_cells(f.read())

    #Writes a new file that outputs the names and addresses of the scanned targets
    with open(file_path, "w") as f:

        #iterates through each cell in the list
        #each cell contains an list of values outputted by the scan
        for cell in cell_list:
            
            #if the name of the address has no name, change it to no name
            strname = get_name(cell)
            if strname == "":
                strname = "N/A"
            
            #Write the contents to the file, which is read by the GUI
            f.write(strname + " - ")
            f.write(get_address(cell))
            f.write("\n")
            
                

def get_scan_results(root, list_box):
    file_path=os.path.dirname(__file__) + "/../data/scan_results.txt"
    
    results = ""
    
    if GUI.MainGUI.host_list_update == True:
        print("Updating host list...")
        with open(file_path, "r") as f:        
            for line in f:
                list_box.insert(END, line)
            GUI.MainGUI.host_list_update = False
            
    
    
    root.after(500, lambda: get_scan_results(root, list_box))
    print(results)

    return results