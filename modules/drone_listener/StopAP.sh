#!/bin/bash

# Usage: sudo ./StopAP.sh

systemctl stop hostapd dnsmasq

echo "Services stopped successfully."

