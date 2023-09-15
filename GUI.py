import tkinter
from tkinter import ttk
import sv_ttk
from ctypes import *
import colors

class GUI:
    def __init__(self, root):
        self.root = root
        root.title("INDRA")
        root.geometry("1200x675")
        root.resizable(False, False)
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(0, weight=1)
        sv_ttk.set_theme("dark")
        
        # change the Icon in the title bar
        root.iconbitmap("high_res_icon.ico")    
        
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
        
        
        # TOP BOX ---------------------------------------------------------------

        self.top_box = ttk.Frame(root, padding=(3, 3, 12, 12), style="box.TFrame")
        self.top_box.pack(fill=tkinter.X, expand=True)
        self.top_box.grid(
            row=0, column=0, sticky="nwe", padx=5, pady=5
        )
        
        greet_button = ttk.Button(self.top_box, text="Greet", command=self.greet)
        greet_button.grid(row=0, column=0, pady=5, padx=5)

        close_button = ttk.Button(self.top_box, text="Close", command=root.quit)
        close_button.grid(row=0, column=1, pady=5)
        
        # END TOP BOX ----------------------------------------------------------
        
        # LEFT BOX --------------------------------------------------------------
        
        self.side_box = ttk.Frame(root, padding=(3, 3, 12, 12), style="box.TFrame")
        self.side_box.grid(
            row=1, column=0, sticky="", padx=5, pady=5,
            columnspan=2, rowspan=4
        )
        
        close_button = ttk.Button(self.side_box, text="Close", command=root.quit)
        close_button.grid(row=0, column=0, pady=5)
        
        # END LEFT BOX ----------------------------------------------------------

    def greet(self):
        print("Greetings!")