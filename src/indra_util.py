from tkinter import ACTIVE
import GUI
import main
import scan

def terminal_out(root, var, value):
    var.set(value)
    
    print(value)
    root.after(500, lambda: terminal_out(root, var, value))
    
def update_info(root, list_box, target_label, target_info_label):
    string = list_box.get(ACTIVE)
    print(f"Active target: {string}")
    
    get_target_info(string)
    
    target_info(root, target_label, target_info_label, string)
    root.after(500, lambda: update_info(root, list_box, target_label, target_info_label))
    
def target_info(root, target_label, target_info_label, string):
    target_label.configure(text=f"Target: {string}")
    target_label.update()
    
    target_info_label.configure(text="Quality: \n"\
                                    "Channel: \n"\
                                    "Signal Level: \n"\
                                    "Encryption: ")
    
def get_target_info(cell_name):
    info_dictionary = scan.cell_info
    
    for i in info_dictionary:
        print(i) 
    
    
    print(f"looking for {cell_name}")
    if cell_name in info_dictionary:
        print(f"Target info: {info_dictionary[cell_name]}")
    else: 
        print("Target not found")
    
    
def updateables(root, **kwargs):
    terminal_out(root, kwargs.get("terminal_output_var"), kwargs.get("terminal_output_var"))
    update_info(root, kwargs.get("host_list_data_box"), kwargs.get("target_label"), kwargs.get("target_info_label"))
    scan.get_scan_results(root, kwargs.get("host_list_data_box"))