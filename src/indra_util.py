from tkinter import ACTIVE
import GUI
import main
import scan

def terminal_out(root, var, value):
    var.set(value)
    
    print(value)
    root.after(500, lambda: terminal_out(root, var, value))
    
def update_info(root, list_box, target_label):
    string = list_box.get(ACTIVE)
    print(string)
    print("test")
    
    #root.setvar(name="current_target", value=string)
    target_label.configure(text=f"Target: {string}")
    target_label.update()
    root.after(500, lambda: update_info(root, list_box, target_label))
    
def updateables(root, **kwargs):
    terminal_out(root, kwargs.get("terminal_output_var"), kwargs.get("terminal_output_var"))
    update_info(root, kwargs.get("host_list_data_box"), kwargs.get("target_label"))
    scan.get_scan_results(root, kwargs.get("host_list_data_box"))