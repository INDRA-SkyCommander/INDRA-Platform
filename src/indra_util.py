from tkinter import ACTIVE
import GUI
import main
import scan

def terminal_out(root, var, value):
    """
    Creates a loop where it is called every 500 milliseconds, updating the tkinter variable then printing its value


    Args:
        root: Tkinter root window
        var: variable to be updated
        value: value to set the variable and print to terminal
    """

    var.set(value)
    
    print(value)
    root.after(500, lambda: terminal_out(root, var, value))

def update_info(root, list_box, target_label, target_info_label):
    """
        Updates information based on the active selection in a set list


        Args:
            root: root window
            list_box: listbox containing target items
            target_label: label to display target name
            target_info_label: label to display target information
    """

    string = list_box.get(ACTIVE)
    print(f"Active target: {string}")
    
    target_info(root, target_label, target_info_label, string)
    root.after(500, lambda: update_info(root, list_box, target_label, target_info_label))

def target_info(root, target_label, target_info_label, string):
    """
         Updates target information labels based on provided string

         Args:
            root: root window
            target_label: label to display the target name
            target_info_label: label to display the information about a target
            string: specific target name
    """

    info_list = get_target_info(string)

    target_label.configure(text=f"Target: {string}")
    target_label.update()
    
    target_info_label.configure(text=f"Quality: {info_list[2]}\n"\
                                    f"Channel: {info_list[3]}\n"\
                                    f"Signal Level: {info_list[4]}\n"\
                                    f"Encryption: {info_list[5]}")
    
def get_target_info(cell_name):
    """
        Retrieves target information from scan results

        Args:
            cell_name: target cell
        
        Returns:
            list containing information about the target cell
    """
    info_dictionary = scan.cell_info


    print(f"looking for {cell_name}")

    if cell_name.strip() in info_dictionary:
        return info_dictionary[cell_name.strip()]
    else: 
        print("Target not found")
        return ['','','','','','']

def toggle_scan_executor(root, interval):
    """
        Executes the scan if toggle is on, otherwise runs itself again after [interval] amount of time

        Args:
            root: root window
            interval: time interval for checking the toggle and executing the scan
    """

    print("Checking for toggle scan")
    if (GUI.MainGUI.switch):
        print("This is the toggle scanning")
        root.after(interval, lambda: scan.scan())
    root.after(interval, lambda: toggle_scan_executor(root, interval))
    
    
    
def updateables(root, **kwargs):
    """
        Updates various elements in the GUI

        Args:
            root: root window
            **kwargs: keyword arguments containing information for updating the GUI components
    """
    terminal_out(root, kwargs.get("terminal_output_var"), kwargs.get("terminal_output_var"))
    update_info(root, kwargs.get("host_list_data_box"), kwargs.get("target_label"), kwargs.get("target_info_label"))
    scan.get_scan_results(root, kwargs.get("host_list_data_box"))
    toggle_scan_executor(root, kwargs.get("interval"))