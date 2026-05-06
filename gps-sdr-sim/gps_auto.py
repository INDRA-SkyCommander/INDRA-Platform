

import os
import datetime
import subprocess
import requests
import gzip
import shutil

NASA_USER = "kab00038"
NASA_PASS = "gb83VfWJu7%*^9PTrs2@"
HACKRF_BIN = "hackrf_transfer"
GPS_SIM_BIN = "./gps-sdr-sim"
WORKING_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

def remove_duplicate_files(directory, string, deleteflag=False):
    if deleteflag:
        try:
            os.remove(find_file(directory, string))
            print(f"[!] Duplicate file removed. ")
        except Exception as e:
            print(f"[!] Error ocurred deleting file: {e}")
            
def find_file(directory, string):
    try:
        for files in os.listdir(directory):
            if string in files:
                return os.path.join(directory, files)
    except Exception as e:
        print(f"[!] Error ocurred finding file: {e}")


def get_gps_date_info():
    # use yesterday to ensure file exists
    now = datetime.datetime.now() - datetime.timedelta(days=1)
    year = now.strftime("%Y")
    yy = now.strftime("%y")
    doy = now.strftime("%j")
    return year, yy, doy

def download_ephemeris(year, yy, doy):
    filename = f"brdc{doy}0.{yy}n.gz"
    if find_file(WORKING_DIRECTORY, filename) != None:
        return
    

    # NASA CDDIS URL Structure
    url = f"https://cddis.nasa.gov/archive/gnss/data/daily/{year}/brdc/{filename}"


    print(f"[*] Downloading {filename} from cddis.nasa.gov...")
    with requests.Session() as session:
        session.auth = (NASA_USER, NASA_PASS)

        response = session.get(url, allow_redirects=True)

        if response.history:
            response = session.get(response.url, auth=(NASA_USER, NASA_PASS))
        if response.status_code == 200 and not response.text.startswith("<!DOCTYPE html>"):
            with open(filename, "wb") as f:
                f.write(response.content)
            print(f"[+] Successfully downloaded {filename}")
        else:
            print("[!] Error: Still receiving HTML or Auth failed.")
            print("Check your NASA username/password and ensure you have 'authorized the CDDIS application in Earthdata.")

        unzipped = filename.replace(".gz", "")
        with gzip.open(filename, 'rb') as f_in:
            with open(unzipped, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        os.remove(filename)
        return unzipped
    
def run_sim(ephem_file, lat, lon, alt):
    remove_duplicate_files(WORKING_DIRECTORY, "gpssim.bin", True)

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
    choice = input("[?] Generation is complete. Start transmitting? Y/N: ")
    if choice.lower() == 'y':
        power = input("Enter transmit power (0-47) (Default is 0): ")
        print("[!] TRANSMITTING... Press CTRL+C to stop.")
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
    y, yy, d = get_gps_date_info()

    ephem = download_ephemeris(y, yy, d)

    if True:
        u_lat = input("Enter Latitude (e.g. 40.7128): ")
        u_lon = input("Enter Longitude (e.g. -74.0060): ")
        u_alt = input("Enter height (m): ")

        
        #run_sim(ephem, u_lat, u_lon, u_alt)
        transmit()

