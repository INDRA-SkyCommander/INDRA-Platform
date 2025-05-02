#!/bin/sh

#
# Copyright (c) 2018, Manfred Constapel
# This file is licensed under the terms of the MIT license.
#

# 
# Pythonic DJI Ryze Tello Workbench: Example
# 
# A simple telemetry script for gathering of data
# from several sensors (and filters), e.g.
#
# - acclerometer and gyroscope (aka IMU)
# - magnetometer (in conjunction with IMU aka AHRS)
# - barometer
# - temperature sensors for overheat protection
# - battery level
# 

#import dependencies 
import json
import socket, sys, signal, time
import os


#size of struc being taken in 
BUFFER_SIZE = 1024
#we only need battery, time of flight, 
STATE = ('mid', 'x', 'y', 'z', 'mpry',
         'pitch', 'roll', 'yaw',
         'vgx', 'vgy', 'vgz',
         'templ', 'temph',
         'tof', 'h', 'bat', 'baro', 'time',
         'agx', 'agy', 'agz')
dictionary = "n"

#parsing into dictionary 
def collect_state(state):
    dic = {k:v for k,v in zip(STATE, ['' for _ in STATE])}
    items = state.split(';')
    pairs = tuple(item.split(':') for item in items)
    values = tuple((pair[0].strip(), pair[-1].strip()) for pair in pairs)
    for i in range(len(values)):
        k, v = values[i][0], values[i][1]
        try: dic[k] = int(v)
        except:
            try: dic[k] = float(v)
            except: pass    
    return dic

def getBat(): 
    return (dictionary['bat'])

def getTH(): 
    return (dictionary['temph'])

def getTof(): 
    return (dictionary['tof'])


if __name__ == '__main__':

    
        

    #write to json file 
    def write(dic, time): 

        """ filename = 'drone_data.json'

        if os.path.exists(filename):
            print(1)
            os.remove(filename) """


        filename = 'src/drone_data.json'
        with open(filename, 'w') as data_file:  # 'x' mode ensures it's created anew
            data = {
                "battery": dic.get('bat'),
                "mid": dic.get('mid'),
                "x": dic.get('x'),
                "y": dic.get('y'),
                "z": dic.get('z'),
                "mpry": dic.get('mpry'),
                "pitch": dic.get('pitch'),
                "roll": dic.get('roll'),
                "yaw": dic.get('yaw'),
                "vgx": dic.get('vgx'),
                "vgy": dic.get('vgy'),
                "vgz": dic.get('vgz'),
                "templ": dic.get('templ'),
                "temph": dic.get('temph'),
                "tof": dic.get('tof'),
                "h": dic.get('h'),
                "baro": dic.get('baro'),
                "time_field": dic.get('time'), 
                "agx": dic.get('agx'),
                "agy": dic.get('agy'),
                "agz": dic.get('agz'),
            }

            print(f"Pitch: {data['pitch']}, Roll: {data['roll']}, Yaw: {data['yaw']}, Battery: {data['battery']}%, TOF: {data['tof']} cm")

            json.dump(data, data_file, indent=5)
    

    #potentially modify remote line

    #socket magic, setup 
    local = ('', 8890)
    remote = ('192.168.10.1', 8889)
    
    #binds to port to receive data 
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)    
    socket.bind(local)
    socket.setblocking(1)

    out = None    

    #try three times, and if no dice, alert
    attempts = 3
    for i in range(attempts):        

        socket.sendto('command'.encode('latin-1'), remote)
        buffer = socket.recv(BUFFER_SIZE)
        out = buffer.decode('latin-1')

        if out == 'ok':
            print('accepted')
            break
        else:
            print('rejected')
            time.sleep(0.5)
            out = None
        
        
    #decode and write 
    startTime = time.time()
    while out:
        buffer = socket.recv(BUFFER_SIZE)
        out = buffer.decode('latin-1')
        out = out.replace('\n', '')
        dic = collect_state(out)
        dictionary = dic
        t = time.time()
        #doing so it doesn't crash the program, or lag
        if(t - startTime > 2): 
            break

        write(dic, t)
        
        """ print('time:{:4d}\tpitch:{:>4}\tbattery:{:>4}\tyaw:{:>4}\tmid:{:>4}\tx:{:>4}\ty:{:>4}\tz:{:>4}\t'
          'mpry:{:>4}\tvgx:{:>4}\tvgy:{:>4}\tvgz:{:>4}\ttempl:{:>4}\ttemph:{:>4}\ttof:{:>4}\th:{:>4}\t'
          'baro:{:>4}\ttime_field:{:>4}\tagx:{:>4}\tagy:{:>4}\tagz:{:>4}'.format(
          int((t - int(t)) * 1000), dic['pitch'], dic['bat'], dic['yaw'], dic['mid'], dic['x'], dic['y'], dic['z'],
          dic['mpry'], dic['vgx'], dic['vgy'], dic['vgz'], dic['templ'], dic['temph'], dic['tof'], dic['h'],
          dic['baro'], dic['time'], dic['agx'], dic['agy'], dic['agz']),
          file=sys.stdout, flush=True) """


        #dictionary = dic

    print('exit')
