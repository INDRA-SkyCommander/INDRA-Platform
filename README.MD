<!-- Banner GIF -->
<img src="https://media.giphy.com/media/UGWpLb1b4KddktMz0y/giphy.gif" width="100%" />

## Quick local setup (fresh system)

From repository root (`INDRA-Platform/`):

```bash
sudo apt update
sudo apt install -y python3 python3-pip gcc make hackrf
pip3 install -r requirements.txt
```

Build the included `gps-sdr-sim` binary:

```bash
cd gps-sdr-sim
make
cd ..
```

Optional NASA CDDIS credentials for ephemeris downloads:

```bash
export NASA_USER="your_earthdata_username"
export NASA_PASS="your_earthdata_password"
```

Start INDRA:

```bash
./INDRA-Start.sh
```

## Steps to set up the VM
- Navigate to INDRA Google Drive
- Find the folder `Environment *.OVAs`
- Download `Indra OVA.ova`
- Import it into VirtualBox

## Before you start the VM
Go to **Settings → Display** and uncheck **Enable 3D Acceleration**.

## Once you start the VM, the password is `indra`
 - make sure to `git pull` to update any code that might have been pushed
 - if any libraries refuse to be recognized after install, install them again with `sudo` and try again
