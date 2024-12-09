#!/bin/bash

if [[ $(id -u) -ne 0 ]] ; then echo "This script must be run with root privileges." ; exit 1 ; fi

self=$(basename "${0}")

usage() { 
    echo
    echo "Usage: "${self}" <option>" 
    echo
    echo "Options:"
    echo "    monitor       : enter monitor mode"
    echo "    managed       : switch to managed mode"
    echo "    info          : show satus of interface"
    echo "    list          : list access points"
    echo "    set <channel> : set channel"
    echo "    help          : show this text"
    echo
} 

if [ $# -lt 1 ]; then usage ; exit 1 ; fi

hash systemctl 2>/dev/null || { echo >&2 "systemctl is not installed."; exit 1; }
hash ip 2>/dev/null || { echo >&2 "ip is not installed."; exit 1; }
hash iwconfig 2>/dev/null || { echo >&2 "iwconfig is not installed."; exit 1; }

dev=$(iwconfig 2> /dev/null | grep 'IEEE 802.11' | grep 'ESSID:off/any' | cut -d' ' -f1 | tail -n1)
if [ -z "${dev}" ] ; then
  dev=$(iwconfig 2> /dev/null | grep 'IEEE 802.11' | cut -d' ' -f1 | tail -n1)
  if [ -z "${dev}" ] ; then
    dev=$(iwconfig 2> /dev/null | grep 'unassociated' | cut -d' ' -f1 | tail -n1)
  fi
fi

case "${1}" in
    managed)
        if [ -z "${dev}" ] ; then
            echo "No wireless interface in monitor mode was found." ;
        else 
            echo "Using interface ${dev}, going managed ..."
            ip link set "${dev}" down
            iw "${dev}" set type managed  # iwconfig "${dev}" mode managed
            ip link set "${dev}" up
        fi
        echo "Restarting services ..."
        systemctl unmask NetworkManager 2> /dev/null
        systemctl restart wpa_supplicant
        systemctl restart NetworkManager
    ;;
    monitor)
        echo "Using interface ${dev}, going monitored, stopping services ..."
        systemctl mask NetworkManager 2> /dev/null
        systemctl stop NetworkManager
        systemctl stop wpa_supplicant
        ip link set "${dev}" down
        iw "${dev}" set monitor none  # iwconfig "${dev}" mode monitor
        ip link set "${dev}" up
    ;;
    list)
        airodump-ng "${dev}"
        iw "${dev}" info        
    ;;
    help)
        usage
    ;;
    set)
        iw dev "${dev}" set channel "${2}"  # iwconfig "${dev}" channel "${2}"
        iw "${dev}" info        
    ;;
    info)
        iw "${dev}" info        
    ;;
    *)
        echo "Invalid argument."
        exit 1
    ;;
esac