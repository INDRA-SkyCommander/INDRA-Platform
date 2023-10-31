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
    
    target_info(root, target_label, target_info_label, string)
    root.after(500, lambda: update_info(root, list_box, target_label, target_info_label))
    
def target_info(root, target_label, target_info_label, string):

    info_list = get_target_info(string)

    target_label.configure(text=f"Target: {string}")
    target_label.update()
    
    target_info_label.configure(text=f"Quality: {info_list[2]}\n"\
                                    f"Channel: {info_list[3]}\n"\
                                    f"Signal Level: {info_list[4]}\n"\
                                    f"Encryption: {info_list[5]}")
    
def get_target_info(cell_name):
    info_dictionary = scan.cell_info

    
    print(f"looking for {cell_name}")

    if cell_name.strip() in info_dictionary:
        return info_dictionary[cell_name.strip()]
    else: 
        print("Target not found")
        return ['','','','','','']
#Executes the scan if toggle is on, otherwise runs itself again after [interval] amount of time
def toggle_scan_executor(root, interval):
    print("Checking for toggle scan")
    if (GUI.MainGUI.switch):
        print("This is the toggle scanning")
        root.after(interval, lambda: scan.scan())
    root.after(interval, lambda: toggle_scan_executor(root, interval))
    

def updateables(root, **kwargs):
    terminal_out(root, kwargs.get("terminal_output_var"), kwargs.get("terminal_output_var"))
    update_info(root, kwargs.get("host_list_data_box"), kwargs.get("target_label"), kwargs.get("target_info_label"))
    scan.get_scan_results(root, kwargs.get("host_list_data_box"))
    toggle_scan_executor(root, kwargs.get("interval"))