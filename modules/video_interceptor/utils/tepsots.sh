#!/bin/bash

if [[ $(id -u) -ne 0 ]] ; then echo "This script must be run with root privileges." ; exit 1 ; fi

#this sets the variable self to the name of the script being executed, without any directory path information
#basename extracts the filename from a given path
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

#check if an argument is provided for the script
#if not, it calls the usage function to display the usage information and exits with a status code of 1
if [ $# -lt 1 ]; then usage ; exit 1 ; fi

#check if the required commands are available on the system
#otherwise we exit with a status of 1
hash systemctl 2>/dev/null || { echo >&2 "systemctl is not installed."; exit 1; }
hash ip 2>/dev/null || { echo >&2 "ip is not installed."; exit 1; }
hash iwconfig 2>/dev/null || { echo >&2 "iwconfig is not installed."; exit 1; }

#Finding wireless interface using iwconfig, which displays wireless interface information
#we use iwconfig to list interfaces an grep the lines using IEEE 802.11 to get the wireless ones
#we use cut to grab the first space delimited name which is the interface name and then use tail to grab the last entry
dev=$(iwconfig 2> /dev/null | grep 'IEEE 802.11' | grep 'ESSID:off/any' | cut -d' ' -f1 | tail -n1)
if [ -z "${dev}" ] ; then
  dev=$(iwconfig 2> /dev/null | grep 'IEEE 802.11' | cut -d' ' -f1 | tail -n1)
  if [ -z "${dev}" ] ; then
    dev=$(iwconfig 2> /dev/null | grep 'unassociated' | cut -d' ' -f1 | tail -n1)
  fi
fi


case "${1}" in
    #swicthes the interface to managed mode
    managed)
        #used to see fi interface is in managed mode already
        if [ -z "${dev}" ] ; then
            echo "No wireless interface in monitor mode was found." ;
        #otherwise we set to managed mode and go about with out day
        else 
            echo "Using interface ${dev}, going managed ..."
            #brings interface down because we cant switch to managed mode if we haven't turned off the device yet
            ip link set "${dev}" down
            #we set the status to managed
            iw "${dev}" set type managed  # iwconfig "${dev}" mode managed
            #brings interface up after turning on managed mode
            ip link set "${dev}" up
        fi
        echo "Restarting services ..."
        #we then unmask the networkmanager to allow it to start back up again
        systemctl unmask NetworkManager 2> /dev/null
        #we restart the WPA encryption service
        systemctl restart wpa_supplicant
        #we restart networkmanger to get wifi up and going again
        systemctl restart NetworkManager
    ;;
    monitor)
        echo "Using interface ${dev}, going monitored, stopping services ..."
        #we mask the networkmanager to prevent startup
        systemctl mask NetworkManager 2> /dev/null
        #we then stop the networkmanager to allow for the new device to be monitored and not have any interfering processes
        systemctl stop NetworkManager
        #stop the wpa encryption
        systemctl stop wpa_supplicant
        #turn of the interface
        ip link set "${dev}" down
        #turn on monitor mode in the interface
        iw "${dev}" set monitor none  # iwconfig "${dev}" mode monitor
        #turn the interface device back on
        ip link set "${dev}" up
    ;;
    list)
        #this command will have the interface start scannning for 802.11 packets over the network you are connected to (it needs monitor mode enabled to work)
        airodump-ng "${dev}"
        #once the previous command has quit, this line will run in the program showing the status of the device in monitor mode
        iw "${dev}" info        
    ;;
    help)
    #calls some script named usage that I have not found yet... (i think)
        usage
    ;;
    set)
        #this command will set the channel for the wireless interface
        #if we don't find an interface  or have no channel to switch to, we print an error message?
        if [ -z "${dev}" ] || [ -z "${2}" ]; then
            echo "Usage: ${self} set <channel>" >&2
            exit 1
        fi
        #turn off the interface if we fail this check
        ip link set "${dev}" down || exit 1
        #if we don't fail the checks, we set the channel to the specified value
        #if we can't set the channel we bring the interface back up and then exit the method
        if ! iw dev "${dev}" set channel "${2}"; then
            ip link set "${dev}" up
            exit 1
        fi
        #if we can turn the interface back on we will, otherwise we exit
        ip link set "${dev}" up || exit 1
        #show the result of the interface state to confirm the channel update successfully occured
        iw "${dev}" info
    ;;
    info)
    #shows us the info of the interface
        iw "${dev}" info        
    ;;
    *)
    #otherwise if the command is not defined, we print an error message
        echo "Invalid argument."
        exit 1
    ;;
esac