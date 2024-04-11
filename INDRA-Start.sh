#!/bin/bash
echo > data/raw_output.txt
echo > data/scan_results.txt
SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )/src/main.py" 
sudo python3 $SCRIPTPATH
