#!/bin/bash
rm data/raw_output.txt
rm data/scan_results.txt
touch data/raw_output.txt
touch data/scan_results.txt
SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )/src/main.py" 
sudo python3 $SCRIPTPATH
