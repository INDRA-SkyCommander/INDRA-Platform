import os
import shutil
import subprocess
import tkinter
from tkinter import END, StringVar, Tk, TkVersion, ttk
import sys
import sv_ttk
from ctypes import *
import colors as colors
import scan as scan
import exploit as exploit
import indra_util as indra_util
import threading
import time
from PIL import Image, ImageTk


class MainGUI:
       
    # Declare variables
    global module_options
    module_options = []
    host_list_update = True
    terminal_output_var = None
    selected_host = None
    switch = False
    interval = 1000
    packets = 10000
    scanToggle = False
    isScanning = False
    scanningInterface = ''
    autoScanningCooldown = 12

    # workaround for running the same thread multiple times
    def runScanThread():
        MainGUI.isScanning = True
        scanThread = threading.Thread(target=scan.scan, args=(MainGUI.scanningInterface,))
        scanThread.start()
    
    # scan over and over. utilize cooldown timer to prevent scanning overlap
    # anything less than a 10 sec cooldown is way too chaotic and overwhelms the usb wifi
    def infScanThread():
        if MainGUI.scanToggle and not MainGUI.isScanning:
            MainGUI.isScanning = True
            infiniteScanThread = threading.Thread(target=MainGUI.runScanThread)
            infiniteScanThread.start()
        time.sleep(MainGUI.autoScanningCooldown)
        MainGUI.isScanning = False
        MainGUI.infScanThread()
            
 
    toggleScanThread = threading.Thread(target=infScanThread)
    
    # Add module-required variables to options list
    module_options.append(packets)
    
    def __init__(self, root):
        """Initializes the Graphical User Interface of the INDRA Software

        Args:
            root (Object): The object that contains the top level of the initialization function
        """
        self.root = root
        root.title("INDRA")
        root.geometry("1200x675")
        root.resizable(False, False)
        root.update_idletasks()
        # root.grid_columnconfigure(0, weight=1)
        sv_ttk.set_theme("dark")
        
        # change the Icon in the title bar
        # root.iconbitmap(os.path.dirname(__file__) + "/../media/high_res_icon.ico")
        
        # NOT CURRENTLY WORKING. I'LL FIX IT LATER
        # get the window handle from windows api
        # HWND = windll.user32.GetParent(root.winfo_id())
        # #set attributes to the window handle
        # bar_color = 0x00E77917
        # windll.dwmapi.DwmSetWindowAttribute(HWND,
        #                                     35,
        #                                     byref(c_int(bar_color)),
        #                                     sizeof(c_int))
        
        self.host_list_var = StringVar()
        self.terminal_output_var = StringVar()
        self.terminal_output_var.set("")
        self.current_target = StringVar(root, name="current_target")
        
        frame_style = ttk.Style()
        frame_style.configure("box.TFrame", background=colors.LIGHT_GREY)
        
        inner_frame_style = ttk.Style()
        inner_frame_style.configure("inner_box.TFrame", background=colors.SLATE)

        button_style = ttk.Style()
        button_style.configure("button.TButton", background=colors.SLATE, focuscolor=colors.SLATE)
        button_style.map("button.TButton", background=[("active", colors.SLATE)])
        
        exploit_button_style = ttk.Style()
        exploit_button_style.configure("exploit_button.TButton", foreground=colors.ORANGE)
        
        dropdown_style = ttk.Style()
        dropdown_style.configure("dropdown.TOptionsMenu", background=colors.SLATE)
        
        label_style = ttk.Style()
        label_style.configure("label.TLabel", background=colors.SLATE, foreground=colors.WHITE)
        
        
        # TOP BOX ---------------------------------------------------------------

        # Grey box up top 
        self.top_box = ttk.Frame(root, style="box.TFrame")
        self.top_box.pack(side="top",
                          fill="x",
                          expand=False,
                          pady=5, padx=5, ipadx=5)
        #self.top_box.grid_columnconfigure(0, weight=1)
        
        # invisible frame to hold the menu items
        menu_frame = ttk.Frame(self.top_box, style="box.TFrame")
        menu_frame.pack(side="top", pady=5)

        # menu items left -> right

        # TOGGLE SCAN BUTTON
        togglescan_button = tkinter.Button(menu_frame,
                                text="Toggle Scan",
                                command=lambda: live_toggle(),
                                relief="flat",
                                background = colors.TKINTER_SLATE,
                                justify="center",
                                font=("Segoe UI", 10))
        togglescan_button.pack(side="left", padx=5)

        # TOGGLE SCAN
        def live_toggle():
            if(MainGUI.scanToggle):
                MainGUI.scanToggle = False
                togglescan_button.config(bg = colors.TKINTER_SLATE,
                                         activebackground = colors.TKINTER_SLATE)
            else:
                MainGUI.scanToggle = True
                togglescan_button.config(bg = colors.ORANGE,
                                         activebackground=colors.ORANGE)
                
        # SCAN BUTTON
        # start scan thread when pressed
        scan_button = ttk.Button(menu_frame,
                                text="Scan",
                                command=lambda: MainGUI.runScanThread(),
                                style="button.TButton")
        scan_button.pack(side="left")


        # INTERFACES SELECTION
            
        def show_interfaces(event):
            getInterfaces()
            MainGUI.scanningInterface = interface_dropdown.get()  
        
        def getInterfaces():
            output = subprocess.check_output('ifconfig | cut -d " " -f1', shell=True, text=True).strip()
            return [interface.replace(':', '') for interface in output.splitlines() if interface]

        selected_interface = StringVar(root)
        selected_interface.set('wlan0')
        interface_dropdown = ttk.Combobox(menu_frame, 
                                        values = getInterfaces(),
                                        state = 'readonly',
                                        )
        interface_dropdown.set('wlan0')
        interface_dropdown.bind("<<ComboboxSelected>>", show_interfaces)
        interface_dropdown.pack(side="left", padx=5)
        

        # MODULES DROPDOWN
        selected_module = StringVar(root)
        # selected_module.set("")
        self.modules_dropdown = ttk.Combobox(menu_frame, 
                                        textvariable = selected_module, 
                                        values = [],
                                        state='readonly',
                                        )
        self.modules_dropdown.set("Modules")
        self.modules_dropdown.pack(side="left", padx=5)

        # OPTIONS DROPDOWN
        def show_option(event):
            """
            Will show the desired option based on the currently selected ComboBox item (see options_dropdown)

            Args:
                event (_type_): Binding for options ComboBox (see options_dropdown)
            """
            options_str = options_dropdown.get()
            option_info_label.grid(row=0, column=0, pady=5, padx=[25,25], ipadx=60, sticky="n")

            match options_dropdown.get():
                # case "Packets":
                #     show_options_label()
                #     option_interval.grid(row=1, column=0)
                # case "Interval":
                #     option_interval.grid(row=1, column=0)
                case "Restart Network Adapter":
                    print('Restarting Network Adapter')
                    os.system("sudo service NetworkManager restart")
                case "Stop Monitor Mode":
                    print('Stopping Monitor Mode')
                    os.system("sudo airmon-ng stop wlan0")    
                case _:
                    option_interval.grid_remove()
                    option_info_label.grid_remove()
                    
            option_info_label.config(text =f"Option: {options_str}")
                    
            
        selected_option = StringVar(root)
        selected_option.set("")
        options_dropdown = ttk.Combobox(menu_frame, 
                                        textvariable = selected_option, 
                                        values = ["Interval", "Packets", "Restart Network Adapter", "Stop Monitor Mode"],
                                        state = 'readonly',
                                        )
        options_dropdown.set("Options")
        options_dropdown.bind("<<ComboboxSelected>>", show_option)
        options_dropdown.pack(side="left", padx=5)


        def runExploitThread():
            exploitThread = threading.Thread(target=exploit.run_exploit, args=(selected_module.get(),))
            exploitThread.start()

        # EXPLOIT BUTTON
        exploit_button = tkinter.Button(menu_frame,
                                text="EXPLOIT",
                                command=lambda: runExploitThread(),
                                bg=colors.ORANGE,
                                relief="flat",
                                activebackground=colors.ORANGE,
                                highlightcolor=colors.LIGHT_ORANGE,
                                justify="center",
                                font=("Segoe UI", 30))
        exploit_button.pack(side="left", padx=5)
        
        # END TOP BOX ----------------------------------------------------------
        
        # LEFT BOX --------------------------------------------------------------
        
        # Grey box on the left
        self.side_box = ttk.Frame(root, padding=(5, 5, 10, 10), style="box.TFrame")
        self.side_box.pack(side="left", fill="y", expand=False, padx=5, pady=5,)
        
        
        # Host List title
        host_list_label = ttk.Label(self.side_box, text="Host List")
        host_list_label.configure(anchor="center",
                                  font=("default", 16, "bold"),
                                  foreground=colors.WHITE)
        host_list_label.grid(row=0, column=0, pady=5, padx=[30,30], ipadx=50, sticky="n")
        
        
        self.inner_side_box = ttk.Frame(self.side_box, padding=(5, 5, 10, 10), style="inner_box.TFrame")
        self.inner_side_box.grid(row=1, column=0, pady=5, padx=[30,30], sticky="n")   
        
        # list box of IPs
        self.host_list_data_box = tkinter.Listbox(self.inner_side_box, width=30, height=30)
        self.host_list_data_box.configure(justify="left",
                                     font=("Segoe UI", 10),
                                     highlightcolor=colors.LIGHT_ORANGE,
                                     fg=colors.WHITE,
                                     selectbackground=colors.LIGHT_ORANGE,
                                     selectforeground=colors.WHITE,
                                     highlightthickness=0,
                                     borderwidth=0,
                                     selectmode="single",
                                     relief="flat",)
        self.host_list_data_box.grid(row=0, column=0, pady=5, padx=[30,30], ipadx=30, sticky="n")
        
        # END LEFT BOX ----------------------------------------------------------
        
        
        
        # CENTER BOX ------------------------------------------------------------
        self.center_box = ttk.Frame(root, style="box.TFrame")
        self.center_box.pack(side="top",
                          fill="x",
                          expand=False,
                          pady=5, padx=5, ipadx=5)
        
        # invisible frame to hold items
        center_frame = ttk.Frame(self.center_box, style="box.TFrame")
        center_frame.pack(side="top", pady=5)
        
        info_label = ttk.Label(center_frame, text="Information")
        info_label.configure(anchor="center",
                             font=("default", 16, "bold"),
                             foreground=colors.WHITE)
        info_label.grid(row=0, column=0, pady=5, padx=[250,250], ipadx=80, sticky="n")
        
        self.Target_label = ttk.Label(center_frame, text=f"Target: {self.current_target}")
        self.Target_label.configure(anchor="center",
                             font=("default", 12),
                             foreground=colors.WHITE)
        self.Target_label.grid(row=1, column=0, pady=5, padx=[30,30], ipadx=50, sticky="nw")
        
        self.Target_info_label = ttk.Label(center_frame,
                                           text="Quality: \n"\
                                                "Channel: \n"\
                                                "Signal Level: \n"\
                                                "Encryption: ")
        self.Target_info_label.configure(anchor="center",
                                font=("default", 12),
                                foreground=colors.WHITE)
        self.Target_info_label.grid(row=2, column=0, pady=5, padx=[30,30], ipadx=50, sticky="nw")
        
        # Center bottom frame to hold options
        center_frame_bottom = ttk.Frame(self.center_box, style="box.TFrame")
        center_frame_bottom.pack(side="bottom", pady=5)
        
        # OPTIONS LABEL
        option_info_label = ttk.Label(center_frame_bottom, text="Options")
        option_info_label.configure(anchor="center",
                             font=("default", 16, "bold"),
                             foreground=colors.WHITE)
        
        
        # INTERVAL OPTION
        option_interval = tkinter.Scale(center_frame_bottom,
                                    variable = self.interval,
                                    from_= 1000,
                                    to= 100000,
                                    orient="horizontal",
                                    length = 400
                                    )
        
        
        
        # END CENTER BOX --------------------------------------------------------
        
        # TERMINAL BOX ----------------------------------------------------------
    
        # Grey box on the bottom
        self.bottom_box = ttk.Frame(root, style="box.TFrame")
        self.bottom_box.pack(side="bottom",
                          fill="x",
                          expand=False,
                          pady=5, padx=5, ipadx=5)
        self.bottom_box.grid_columnconfigure(0, weight=1)
 
        # Terminal title
        host_list_label = ttk.Label(self.bottom_box, text="Terminal Output")
        host_list_label.configure(anchor="center")
        host_list_label.grid(row=0, column=0, pady=5, padx=[30,30], ipadx=50)
        
        # grey box around terminal output
        self.inner_bottom_box = ttk.Frame(self.bottom_box, padding=(5, 5, 10, 10), style="inner_box.TFrame")
        self.inner_bottom_box.grid(row=1, column=0, pady=[10,20], padx=[30,30], sticky="n")
        
        # Terminal output
        terminal_output_label = ttk.Label(self.inner_bottom_box, width=20, textvariable=self.terminal_output_var.get())
        terminal_output_label.configure(anchor="center")
        terminal_output_label.grid(row=0, column=0, pady=5, padx=[30,30], ipadx=30, sticky="n")
        
        # END TERMINAL BOX ------------------------------------------------------

        indra_util.updateables(root,
                               terminal_output_var=self.terminal_output_var,
                               host_list_data_box=self.host_list_data_box,
                               current_target=self.current_target,
                               target_label=self.Target_label,
                               target_info_label=self.Target_info_label,
                               interval=self.interval,
                               module_dropdown=self.modules_dropdown)
        
        MainGUI.toggleScanThread.start()

        def videoPlayer():
            image_folder = "../data/images"  # Adjust this to your image folder path
            self.image_player = ImagePlayer(root, image_folder=image_folder, frame_rate=2)
            self.image_player.stop()
            self.image_player.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        videoPlayer()       

        root.mainloop()       

    def fill_host_list(self, host_list_file, host_list_box):
        """Will populate the INDRA software's host_list_box tkinter widget with the host_list_file Object

        Args:
            host_list_file (Object): Contains the file path to the formatted host list
            host_list_box (Tkinter): A tkinter widget that displays the currently available targets
        """
        for line in host_list_file:
            host_list_box.insert(END, line)
    
    # Helper function to obtain options
    def get_module_options():
        """Returns a list containing options to be outputted to the module_input_data.json file

        Returns:
            list: List of option variables to be outputted to the module_input_data.json file
        """
        return module_options
    
# Image Player class for gui video player    
import os
import shutil
from PIL import Image, ImageTk
from tkinter import ttk


class ImagePlayer(ttk.Frame):
    """
    A widget to display images from a folder at a specific frame rate.
    """

    def __init__(self, parent, image_folder, frame_rate=2):
        super().__init__(parent)
        self.frame_rate = frame_rate
        self.image_folder = image_folder
        self.images = []  # List of all images in the folder
        self.new_images = []  # List of newly added images
        self.current_image_index = 0
        self.paused = True

        self.label = ttk.Label(self)
        self.label.pack(expand=True, fill="both")

        current_dir = os.path.dirname(__file__)
        data_folder = os.path.join(current_dir, "..", "data")
        image_folder = os.path.join(data_folder, "images")
        os.makedirs(image_folder, exist_ok=True)
        
        self._clear_folder()
        self.load_images()
        self.monitor_folder()
        
    def _clear_folder(self):
        """Clears the contents of the image folder."""
        
        if os.path.exists(self.image_folder):
            for filename in os.listdir(self.image_folder):
                file_path = os.path.join(self.image_folder, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)  # Remove file or symbolic link
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)  # Remove folder
                except Exception as e:
                    print(f"Failed to clear {file_path}. Reason: {e}")

    def load_images(self):
        """Loads all images from the folder and identifies new images."""
        all_images = [
            os.path.join(self.image_folder, f)
            for f in sorted(os.listdir(self.image_folder))
            if f.lower().endswith(('.png', '.jpg', '.jpeg'))
        ]
        # Identify new images by excluding already loaded ones
        new_images = [img for img in all_images if img not in self.images]
        self.images.extend(new_images)  # Update the full list of images
        self.new_images.extend(new_images)  # Keep track of only new images

    def monitor_folder(self):
        """
        Continuously checks for newly added images in the folder.
        If new images are found, they are added to the playback list.
        """
        self.load_images()
        if self.new_images and self.paused:
            self.start()
        self.after(1000, self.monitor_folder)  # Check every second

    def play_images(self):
        """Plays only the newly added images one by one at the specified frame rate."""
        if not self.paused and self.new_images:
            img_path = self.new_images.pop(0)  # Pop the first image in the new list
            try:
                img = Image.open(img_path)
                img = img.resize((730, 300))  # Resize to fit
                img = ImageTk.PhotoImage(img)
                self.label.config(image=img)
                self.label.image = img
                self.after(int(1000 / self.frame_rate), self.play_images)
            except Exception as e:
                print(f"Error displaying {img_path}: {e}")
        else:
            self.stop()

    def start(self):
        """Starts or resumes playback for newly added images."""
        self.paused = False
        self.play_images()

    def stop(self):
        """Pauses playback."""
        self.paused = True

    def toggle_playback(self):
        """Toggles between play and pause."""
        if self.paused:
            self.start()
        else:
            self.stop()