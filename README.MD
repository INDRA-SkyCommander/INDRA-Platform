
<!-- Banner GIF -->
<img src="https://media.giphy.com/media/UGWpLb1b4KddktMz0y/giphy.gif" width=100% />



### Dependencies 
Run the following command from the same directory as "requirements.txt"
```bash
python3 -m pip install -r requirements.txt
```

### Dev Notes

#### Package dependencies
At the end of your development session, before pushing your changes, run the following command to package up all of the dependencies and output them to "requirements.txt"
```bash
pip freeze > requirements.txt
```

#### GUI
* TKinter is being used to create the GUI, but TKinter looks very outdated. As a simple workaround for this, a theme is being used to easily update the look of the GUI. 
* This means your should use "ttk()" instead of "tk()" in most places.
* Example: 
```py
top_box = ttk.Frame(root, padding=(3, 3, 12, 12), style="box.TFrame")
```

#### VIRTUALBOX SETUP
* Adding USB Network Devices to VirtualBox
* This setup can be used to verify Wireless Communication is responsive in your VirtualBox environment

1. Open VirtualBox Manager and click Settings.

2. Select USB and specify USB Controller.

3. Select either USB 2.0 (EHCI) Controller or USB 3.0 (xHCI) Controller according to your actual hardware.

4. Add USB Device Filters to define the types of USB drives which will be automatically made visible to the guest OS.

5. Start up VirtualBox, right-click on the virtual machine that needs access to a USB device, and click Settings.

6. In the virtual machine’s Setting tab, click on USB to see the available USB devices.

7. Click on the + sign to add a new device. This device should read either Realtek 802.11 NIC, RTL 8812, or equivalent

8. Once USB device added, start up the virtual machine to have access to the data on the USB device.

#### KALI PROJECT DEPENDENCIES SETUP
* Setting up Project Dependencies on a KALI Virtual Machine
* This setup can be used to verify KALI is correctly set up and able to run application

0. BEFORE RUNNING THESE COMMANDS MAKE SURE YOUR KALI IS UPDATED BY RUNNING THIS COMMAND IN TERMINAL
	```terminal
		sudo apt get dist-upgrade -y
	```

1. Run this command in terminal to install appropriate drivers
	```terminal
	sudo apt install realtek-rtl88xxau-dkms
    ```

2. Restart KALI to complete driver installation.

3. Run this command in terminal to complete dkms installation after restart. 
	```terminal 
	sudo apt install dkms
	```

4. Clone the Aircrack GitHub repository onto the local KALI machine
	```terminal
	git clone https://github.com/aircrack-ng/rtl8812au
    ```
	
5. From within the directory of the git repository cloned in the previous step, run the following command in your terminal. This will take a while.
	```terminal
	make
    ```

6. To complete installation of Aircrack, run the following commmand within the same directory
	```terminal
	sudo make install
    ```

7. Restart KALI to complete driver installation.

8. To check for completion of the Aircrack installation, run the following command. If it works, a list of available devices will be shown. If not, none will be available.
	```terminal
	iwconfig
	```

9. To check for completion of the monitor mode within Aircrack, run the following command. If it works, a list of available devices will be shown. If not, none will be available.
	```terminal
	iwlist wlan0 scan
	```
