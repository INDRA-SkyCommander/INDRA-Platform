import os
import random
from tkinter import END

import GUI

def scan():
    print("Beep boop. Scanning....")

    i = random.randint(0,15)

    if i > 6:
        print("Wow! There's definitely a drone here!")
        
        file_path=os.path.dirname(__file__) + "\\..\\data\\scan_results.txt"
        
        with open(file_path, "w") as f:
            for j in range(0,i):
                f.write(".".join(map(str, (random.randint(0, 255) for _ in range(4)))))
                f.write("\n")
                

def get_scan_results(root, var):
    print("Getting scan results...")
    file_path=os.path.dirname(__file__) + "\\..\\data\\scan_results.txt"
    
    results = ""
    
    with open(file_path, "r") as f:
        var.set(f.read())
    
    
    root.after(500, lambda: get_scan_results(root, var))
    print(results)
    return results