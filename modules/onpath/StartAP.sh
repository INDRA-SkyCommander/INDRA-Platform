#!/bin/bash

# Usage: sudo ./StartAP.sh wlx...
if [ $# -eq 0 ]; then
    echo "Error: No argument passed. 
    Usage: sudo $0 <interface>"
    exit 1
fi

IFACE="$1"
MAX_RETRIES=3
ATTEMPT=0

# Set the interface mode to UP
ip link set ${IFACE} up

# Uncomment if you are having issues with the IP range
# ip addr add 192.168.10.1/24 dev ${IFACE}

# Start hostapd and dnsmasq services
systemctl unmask hostapd
systemctl enable hostapd dnsmasq

# Start the services
while [ $ATTEMPT -lt $MAX_RETRIES ]; do
    ERROR=$(systemctl start hostapd dnsmasq 2>&1)

    if echo "$ERROR" | grep -q "control process exited with error code"; then
        echo "Service startup failed, attempt $((ATTEMPT + 1)) of $MAX_RETRIES. Retrying..."
        systemctl stop systemd-resolved.service
        ATTEMPT=$((ATTEMPT + 1))
        sleep 2
    else
        echo "Services started successfully."
        break
    fi
done

if [ $ATTEMPT -eq $MAX_RETRIES ]; then
    echo "Failed to start services after $MAX_RETRIES attempts."
    exit 1
fi

