import tkinter as tk
from gui import MainGUI

# Primary entry point for the application

if __name__ == "__main__":
	root = tk.Tk()
	main_gui = MainGUI(root)

	root.mainloop()
