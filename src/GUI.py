import os
import tkinter
from tkinter import StringVar, Tk, ttk
import sv_ttk
from ctypes import *
import colors as colors
import scan as scan

class GUI:
    def __init__(self, root):
        self.root = root
        root.title("INDRA")
        root.geometry("1200x675")
        root.resizable(False, False)
        # root.grid_columnconfigure(0, weight=1)
        sv_ttk.set_theme("dark")
        
        # change the Icon in the title bar
        root.iconbitmap(os.path.dirname(__file__) + "\\..\\media\\high_res_icon.ico")    
        
        #NOT CURRENTLY WORKING. I'LL FIX IT LATER
        # get the window handle from windows api
        # HWND = windll.user32.GetParent(root.winfo_id())
        # #set attributes to the window handle
        # bar_color = 0x00E77917
        # windll.dwmapi.DwmSetWindowAttribute(HWND,
        #                                     35,
        #                                     byref(c_int(bar_color)),
        #                                     sizeof(c_int))

        frame_style = ttk.Style()
        frame_style.configure("box.TFrame", background=colors.LIGHT_GREY)

        button_style = ttk.Style()
        button_style.configure("button.TButton", background=colors.SLATE)
        
        
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
        scan_button = ttk.Button(menu_frame,
                                text="Scan",
                                command=scan.scan,
                                style="button.TButton")
        scan_button.pack(side="left")

        variable = StringVar(root)
        variable.set("one")
        modules_dropdown = ttk.OptionMenu(menu_frame, variable, "Enumerate", "One", "Two", "Three")
        modules_dropdown.pack(side="left", padx=5)
        # END TOP BOX ----------------------------------------------------------
        
        # LEFT BOX --------------------------------------------------------------
        
        self.side_box = ttk.Frame(root, padding=(5, 5, 10, 10), style="box.TFrame")
        self.side_box.pack(side="left", fill="y", expand=False, padx=5, pady=5)
        
        close_button = ttk.Button(self.side_box, text="Close", command=root.quit)
        close_button.grid(row=0, column=0, pady=5)
        
        # END LEFT BOX ----------------------------------------------------------

    def greet(self):
        print("Greetings!")