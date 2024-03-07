
<!-- Banner GIF -->
<img src="https://media.giphy.com/media/UGWpLb1b4KddktMz0y/giphy.gif" width=100% />

### Documentation
Browse to the following location in a web browser:
```
file:///home/kali/Indra/INDRA-Platform/doxygen/html/namespaces.html
``` 


### Dependencies 
Run the following commands to ensure that all of the correct requirements are installed
```bash
sudo apt-get install python3.11
```
```bash
sudo apt install pip
```
```bash
sudo apt-get install python3-tk
```
```bash
sudo pip3 install sv_ttk
```
```bash
sudo apt-get install hackrf libhackrf-dev libhackrf0
```
```bash
sudo apt install gnuradio
```
```bash
sudo apt install gr-osmosdr
```


### Dev Notes

#### Package dependencies
At the end of your development session, before pushing your changes, update dependencies if any additional requirements are added. In further iterations a bash script will be supplied to install these requirements.

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

#### UBUNTU 20.04.3 LTS PROJECT DEPENDENCIES SETUP
* Setting up Project Dependencies on a Ubuntu 20.04.3 LTS Virtual Machine
* This setup can be used to verify Ubuntu is correctly set up and able to run application

0. BEFORE RUNNING THESE COMMANDS MAKE SURE YOUR UBUNTU IS UPDATED BY RUNNING THIS COMMAND IN TERMINAL
	```terminal
		sudo apt-get update -y
	```
	```terminal
		sudo apt upgrade -y
	```

1. Run this command in terminal to install appropriate drivers
	```terminal
	sudo apt install realtek-rtl88xxau-dkms
    ```

2. Restart Ubuntu to complete driver installation.

3. Run this command in terminal to complete dkms installation after restart. 
	```terminal 
	sudo apt install dkms
	```
4. Restart Ubuntu to complete driver installation.
