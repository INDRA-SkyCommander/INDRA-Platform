import GUI as GUI
import scan

# This is the main file and entry point for the program.
# This guard ensures that the code is only executed when this file is run directly.
if __name__ == "__main__":
    root = GUI.tkinter.Tk()
    main_gui = GUI.GUI(root)
    
    
    root.mainloop()