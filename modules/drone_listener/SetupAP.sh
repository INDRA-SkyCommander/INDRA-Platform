#!/bin/bash

# Usage: sudo ./SetupAP.sh wlx...
if [ $# -eq 0 ]; then
    echo "Error: No argument passed. 
    Usage: sudo $0 <interface>"
    exit 1
fi

IFACE="$1"

# Verify installed dependencies
apt list --installed hostapd dnsmasq

# Create and configure interface config file
touch /etc/network/interfaces.d/${IFACE}
cat > /etc/network/interfaces.d/${IFACE} << EOF
auto ${IFACE}
iface ${IFACE} inet static
  address 192.168.10.1
  netmask 255.255.255.0
EOF

# Write hostapd config
cat > /etc/hostapd/hostapd.conf << EOF
interface=${IFACE}
driver=nl80211
ssid=TELLO-F17756
hw_mode=g
channel=6
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
EOF

# Write dnsmasq config
cat > /etc/dnsmasq.conf << EOF
interface=${IFACE}
dhcp-range=192.168.10.2,192.168.10.10,255.255.255.0,24h
domain-needed
bogus-priv
EOF

# Set hostapd conf file
echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' >> /etc/default/hostapd

# Prepare the interface to run the AP
ip link set ${IFACE} up
ip addr add 192.168.10.1/24 dev ${IFACE}

