import os
import random
from tkinter import END

import GUI
from format import *

def scan():
    print("Beep boop. Scanning....")

    cell_list = [[]]
        
    file_path=os.path.dirname(__file__) + "\\..\\data\\scan_results.txt"

    scan_file_path=os.path.dirname(__file__) + "\\..\\data\\monitorscan2.txt"

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
            f.write("\n\n")
                

def get_scan_results(root, var):
    print("Getting scan results...")
    file_path=os.path.dirname(__file__) + "\\..\\data\\scan_results.txt"
    
    results = ""
    
    with open(file_path, "r") as f:
        var.set(f.read())
    
    
    root.after(500, lambda: get_scan_results(root, var))
    print(results)

    return results