#!/bin/sh
'''which' python3 > /dev/null && exec python3 "$0" "$@" || exec python "$0" "$@"
'''

#
# Copyright (c) 2019, Manfred Constapel
# This file is licensed under the terms of the MIT license.
#

#
# Tapping IEEE-802.11 Packet Sniffer on the Socks
#

import os, sys, socket, time, signal, argparse, enum, datetime

# ------------------------------------------

def split(value, size=2):
    return tuple(value[0 + i:size + i] for i in range(0, len(value), size))


def hex2dec(value):
    if type(value) == str:
        value = value.strip()
        if ' ' not in value:
            return int(value, 16)
        else:
            return hex2dec(value.split(' '))
    else:
        return tuple(int(item, 16) for item in value)


def dec2hex(value, delim=''):
    if type(value) == int:
        s = hex(value)
        return '0' * (len(s) % 2) + s[2:]     
    else:
        return delim.join(dec2hex(item, delim) for item in value) 

# ------------------------------------------

def log(e, more=None, head=None, out=sys.stdout):
    fn = os.path.split(sys.exc_info()[-1].tb_frame.f_code.co_filename)[-1]
    ln = sys.exc_info()[-1].tb_lineno
    print('{} {} : {} {} : {} {} {}'.format(
        '{}'.format(str(head)) if head is not None else '',
        time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()),
        type(e).__name__, str(e), fn, ln,
        ': {}'.format(str(more)) if more is not None else '').strip(),
        file=out, flush=True)

# ------------------------------------------

RT_FIELD = (
    ((8, 'TSFT'),),                                          # (0)  ms              x
    ((1, 'Flags'),),                                         # (1)  bitmap          x
    ((1, 'Rate'),),                                          # (2)  500 kb/s
    ((2, 'Channel'), (2, 'Channel flags'),),                 # (3)  MHz, bitmap     x
    ((2, 'FHSS'),),                                          # (4)
    ((1, 'Antenna signal'),),                                # (5)  dBm             x
    ((1, 'Antenna noise'),),                                 # (6)  dBm
    ((2, 'Lock quality'),),                                  # (7)
    ((2, 'TX attenuation'),),                                # (8)
    ((2, 'dB TX attenuation'),),                             # (9)  dB
    ((1, 'dBm TX power'),),                                  # (10) dBm
    ((1, 'Antenna'),),                                       # (11) index           x
    ((1, 'dB antenna signal'),),                             # (12) dB
    ((1, 'dB antenna noise'),),                              # (13) dB
    ((2, 'RX flags'),),                                      # (14) bitmap          x
    ((2, None),),                                            # (15)
    ((1, None),),                                            # (16)
    ((1, 'data retries'),),                                  # (17)
    ((4, None), (4, None),),                                 # (18)
    ((1, 'MCS known'), (1, 'MCS flags'), (1, 'MCS index')),  # (19) bitmap          x
)


RT_MCS = (  # mcsindex=[0-31] bandwidth=[0-3] guardinterval[0,1]
    # 802.11n                         802.11ac
    # 20 MHz          40 MHz          80 MHz        160 MHz
    ((  6.5,   7.2), ( 13.5,  15.0), (None, None), (None, None)),
    (( 13.0,  14.4), ( 27.0,  30.0), (None, None), (None, None)),
    (( 19.5,  21.7), ( 40.5,  45.0), (None, None), (None, None)),
    (( 26.0,  28.9), ( 54.0,  60.0), (None, None), (None, None)),
    (( 39.0,  43.3), ( 81.0,  90.0), (None, None), (None, None)),
    (( 52.0,  57.8), (108.0, 120.0), (None, None), (None, None)),
    (( 58.5,  65.0), (121.5, 135.0), (None, None), (None, None)),
    (( 65.0,  72.2), (135.0, 150.0), (None, None), (None, None)),

    (( 13.0,  14.4), ( 27.0,  30.0), (None, None), (None, None)),
    (( 26.0,  28.9), ( 54.0,  60.0), (None, None), (None, None)),
    (( 39.0,  43.3), ( 81.0,  90.0), (None, None), (None, None)),
    (( 52.0,  57.8), (108.0, 120.0), (None, None), (None, None)),
    (( 78.0,  86.7), (162.0, 180.0), (None, None), (None, None)),
    ((104.0, 115.6), (216.0, 240.0), (None, None), (None, None)),
    ((117.0, 130.3), (243.0, 270.0), (None, None), (None, None)),
    ((130.0, 144.4), (270.0, 300.0), (None, None), (None, None)),

    (( 19.5,  21.7), ( 40.5,  45.0), (None, None), (None, None)),
    (( 39.0,  43.3), ( 81.0,  90.0), (None, None), (None, None)),
    (( 58.5,  65.0), (121.5, 135.0), (None, None), (None, None)),
    (( 78.0,  86.7), (162.0, 180.0), (None, None), (None, None)),
    ((117.0, 130.0), (243.0, 270.0), (None, None), (None, None)),
    ((156.0, 173.3), (324.0, 360.0), (None, None), (None, None)),
    ((175.5, 195.0), (364.5, 405.0), (None, None), (None, None)),
    ((195.0, 216.7), (405.0, 450.0), (None, None), (None, None)),

    (( 26.0,  28.8), ( 54.0,  60.0), (None, None), (None, None)),
    (( 52.0,  57.6), (108.0, 120.0), (None, None), (None, None)),
    (( 78.0,  86.8), (162.0, 180.0), (None, None), (None, None)),
    ((104.0, 115.6), (216.0, 240.0), (None, None), (None, None)),
    ((156.0, 173.2), (324.0, 360.0), (None, None), (None, None)),
    ((208.0, 231.2), (432.0, 480.0), (None, None), (None, None)),
    ((234.0, 260.0), (486.0, 540.0), (None, None), (None, None)),
    ((260.0, 288.8), (540.0, 600.0), (None, None), (None, None)),
)


def dissect_radiotap(raw):
    
    fids = ('Rate', 'Channel', 'Antenna signal', 'MCS known', 'MCS flags', 'MCS index')
    
    size = raw[3] << 8 | raw[2] << 0
    presence = raw[7] << 24 | raw[6] << 16 | raw[5] << 8 | raw[4] << 0    
    p = 8
    
    extended = presence & (1 << 31) != 0
    while extended:
        temp = raw[p+3] << 24 | raw[p+2] << 16 | raw[p+1] << 8 | raw[p+0] << 0
        p += 4
        extended = temp & (1 << 31) != 0    
    
    #head, mask, data = raw[:4], raw[4:p], raw[p:size]
    data = raw[p:size]
    
    p = 0
    
    fields = {k: None for k in fids}
    for idx, fld in enumerate(RT_FIELD):
        for (ofs, name) in fld:
            if presence & (1 << idx) != 0:  # field is set in mask
                if ofs > 1:
                    p += p % ofs  # set natural boundary, 16-bit field on 16-bit boundary etc.
                if name in fields:
                    fields[name] = sum(b << (i*8) for i, b in enumerate(data[p:p+ofs]))
                p += ofs

    rate, chan, sig = None, None, None

    chan = fields['Channel']

    if fields['Antenna signal'] is not None:
        sig = -(256 - fields['Antenna signal'])  

    if fields['Rate'] is not None:
        rate = fields['Rate'] / 2    
    
    else: 

        if fields['MCS known'] is not None:
            bw, mcs, gi = 0, 0, 0 
            if fields['MCS known'] & (1 << 0) != 0:
                bw = (fields['MCS flags'] & 0b00000011) >> 0
            if fields['MCS known'] & (1 << 1) != 0:
                mcs = fields['MCS index']
            if fields['MCS known'] & (1 << 2) != 0:
                gi = (fields['MCS flags'] & 0b00000100) >> 2
            rate = (mcs, bw, gi)

    return size, (rate, chan, sig)


def dissect_ieee80211(raw):
    ft = (raw[0] & 0b00001100) >> 2  # frame type
    st = (raw[0] & 0b11110000) >> 4  # frame subtype
    ds = (raw[1] & 0b00000011) >> 0  # from-ds, to-ds 
    sa, da = None, None
    sn, fn = None, None
    p = 0
    if ft == 0:  # man
        sa = raw[10:10+6]  # addr2
    if ft == 1:  # con
        da = raw[ 4: 4+6]  # addr1
    elif ft == 2:  # dat  
        if ds & (1 << 0) == 0:
            if ds & (1 << 1) == 0:
                da = raw[ 4: 4+6]  # addr1
                sa = raw[10:10+6]  # addr2
                p = 22 
            else:
                da = raw[ 4: 4+6]  # addr1
                sa = raw[16:16+6]  # addr3
                p = 22 
        else:
            if ds & (1 << 1) == 0:
                sa = raw[10:10+6]  # addr2
                da = raw[16:16+6]  # addr3
                p = 22 
            else:
                da = raw[16:16+6]  # addr3
                sa = raw[22:22+6]  # addr4
                p = 28 
        sc = raw[p+1] << 8 | raw[p] << 0  # sequence control
        sn = (sc & ~0b0000000000001111) >> 4  # sequence
        fn = (sc & 0b0000000000001111) >> 0  # fragment
    return ft, st, sa, da, sn, fn

# ------------------------------------------

def sniff(sources=(), destinations=(), types=(), subtypes=(), length=(), strength=(), verbose=False, fixed=False, readable=False):

    sources = tuple(bytes(hex2dec(split(item))) for item in sources)
    destinations = tuple(bytes(hex2dec(split(item))) for item in destinations)
    
    # filter for destination addresses 
    if len(destinations) == 0: chk_da = lambda x : True
    else: chk_da = lambda x : x in destinations

    # filter for source addresses 
    if len(sources) == 0: chk_sa = lambda x : True
    else: chk_sa = lambda x : x in sources

    # 0=Management, 1=Control, 2=Data, 3=N/A
    if len(types) == 0: chk_ft = lambda x : True
    else: chk_ft = lambda x : x in types 

    # ..., 4=probe request, 5=probe response, ...
    if len(subtypes) == 0: chk_fs = lambda x : True
    else: chk_fs = lambda x : x in subtypes

    # filter for frame length 
    if len(length) == 0: chk_fl = lambda x : True    
    elif len(length) == 1: chk_fl = lambda x : x >= min(length)
    else: chk_fl = lambda x : min(length) <= x <= max(length)

    # filter for signal strength 
    if len(strength) == 0: chk_ss = lambda x : True    
    elif len(strength) == 1: chk_ss = lambda x : x >= min(strength)
    else: chk_ss = lambda x : min(strength) <= x <= max(strength)

    # ------------------------------------------

    if fixed:
        line = lambda t, size, phy, ft, fs, src, dst, fsn, ffn, chan, rate, sig : \
            ' '.join((
            datetime.datetime.fromtimestamp(t).strftime('%H:%M:%S.%f') if readable else '{:.6f}'.format(t),
            '{:1}'.format(phy),
            '{:4d}'.format(size),
            '{:1d}'.format(ft),
            '{:2d}'.format(fs),
            '{:0>12}'.format(dec2hex(src)) if src is not None else ' ' * 12,
            '{:0>12}'.format(dec2hex(dst)) if dst is not None else ' ' * 12,
            '{:4}'.format(fsn) if fsn is not None else ' ' * 4,
            '{:2}'.format(ffn) if ffn is not None else ' ' * 2,
            '{:5}'.format(chan) if chan is not None else ' ' * 5,
            '{:5.1f}'.format(rate) if rate is not None else ' ' * 5,
            '{:3d}'.format(sig) if sig is not None else ' ' * 3,
            )
        )
    else:
        line = lambda t, size, phy, ft, fst, src, dst, fsn, ffn, chan, rate, sig : \
            '{} {} {} {} {} {} {} {} {} {} {} {}'.format(
            datetime.datetime.fromtimestamp(t).strftime('%H:%M:%S.%f') if readable else t,
            phy, size,
            ft, fs,
            dec2hex(src) if src is not None else None,
            dec2hex(dst) if dst is not None else None,
            fsn, ffn,
            chan, rate, sig,
            )

    if verbose:
        amend = lambda data : dec2hex(data)
    else:
        amend = lambda data : ''

    # ------------------------------------------

    BUFFER_SIZE = 4096  # > mtu + mac header + encryption header + any additional stuff
    ETH_P_ALL = 3  # sniff all ethernet protocols, ref. http://man7.org/linux/man-pages/man7/packet.7.html
            
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
    s.bind((args.interface, ETH_P_ALL))
    s.setblocking(1)  # blocking!
    
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    while True:

        t = time.time()
        
        packet = s.recv(BUFFER_SIZE)
        
        if (packet[0:2] != b'\x00\x00'): continue
        
        try:        

            size, (rate, chan, sig) = dissect_radiotap(packet)
            
            data = packet[size:]
            size = size + len(data)   

            if not chk_fl(size): continue
            if not chk_ss(sig): continue
                   
            ft, fs, src, dst, fsn, ffn = dissect_ieee80211(data)
            
            if not chk_sa(src): continue
            if not chk_da(dst): continue
            if not chk_ft(ft): continue
            if not chk_fs(fs): continue

            dt, phy = None, None

            if rate in (1, 2, 5.5, 11):
                phy = 'b'
                dt = int(((size) * 8) / rate)  # rough estimate

            elif type(rate) in (tuple, list):
                if rate[1] < 2: phy = 'n'
                else: phy = 'ac'
                rate = RT_MCS[rate[0]][rate[1]][rate[2]]
                dt = int(((size) * 8) / rate)  # rough estimate

            elif rate is not None:
                phy = 'g'
                dt = int(((size) * 8) / rate)  # rough estimate

            sys.stdout.write('{} {}\n'.format(
                line(t, size, phy, ft, fs, src, dst, fsn, ffn, chan, rate, sig),
                amend(data)))

            sys.stdout.flush()

        except Exception as e:
            log(e, head='(*)', more=dec2hex(packet), out=sys.stderr)


if __name__ == '__main__':
        
    if os.geteuid() != 0:
        print('Ooops, you need root permissions to do this.')
        exit(1)

    parser = argparse.ArgumentParser(description='Tapping IEEE-802.11 Packet Sniffer on the Socks',
                                     epilog='',
                                     add_help=True,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('-i',  '--interface', help='interface to sniff', required=True)
    parser.add_argument('-sa', '--sources', nargs='+', help='source addresses', required=False)
    parser.add_argument('-da', '--destinations', nargs='+', help='destination address', required=False)
    parser.add_argument('-t',  '--types', nargs='+', help='frame types', required=False)
    parser.add_argument('-st', '--subtypes', nargs='+', help='frame subtypes', required=False)
    parser.add_argument('-l',  '--length', nargs='+', help='minimum (and maximum) frame length', required=False)        
    parser.add_argument('-s',  '--strength', nargs='+', help='minimum (and maximum) signal strength', required=False)        
    parser.add_argument('-v',  '--verbose', action='store_true', help='show frame data', default=None)
    parser.add_argument('-f',  '--fixed', action='store_true', help='show at a fixed length', default=None)
    parser.add_argument('-r',  '--readable', action='store_true', help='human-readable timestamps', default=None)

    args = parser.parse_args()

    if args.sources is None: args.sources = []      
    if args.destinations is None: args.destinations = []
    if args.types is None: args.types = []
    if args.subtypes is None: args.subtypes = []
    if args.length is None: args.length = []
    if args.strength is None: args.strength = []
    args.verbose = args.verbose is not None
    args.fixed = args.fixed is not None
    args.readable = args.readable is not None

    try:
        args.types = [int(item) for item in args.types] 
        args.subtypes = [int(item) for item in args.subtypes]
        args.length = [int(item) for item in args.length]
        args.strength = [int(item) for item in args.strength]
    except ValueError as e:
        print(e, file=sys.stderr)
        exit(1)

    sniff(sources=args.sources, destinations=args.destinations,
          types=args.types, subtypes=args.subtypes, length=args.length,
          strength=args.strength, verbose=args.verbose, fixed=args.fixed,
          readable=args.readable)