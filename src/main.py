import tkinter as tk
import sys
import os

# Add parent directory to path so we can import src
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# from src.gui import MainGUI
from src.gui import IndraGUI

# Primary entry point for the application

if __name__ == "__main__":
	#root = tk.Tk()
	#main_gui = MainGUI(root)
	#root.mainloop()
    
	main_gui = IndraGUI()
	main_gui.mainloop()
