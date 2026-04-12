import datetime
import struct
from protocol import PKT_TYPE_FROM_DRONE, build_packet, PKT_TYPE_RESPONSE

def make_conn_ack():
    return b"conn_ack:g+"

def make_status_response(seq_id):
    payload = struct.pack('<24B',
        0x00, 0x00, 0x00, 0x00,  # bytes 0-3
        0x00, 0x00, 0x00, 0x00,  # bytes 4-7
        0x00, 0x00, 0x00, 0x00,  # bytes 8-11
        0x00, 0x00, 0x4e, 0x00,  # bytes 12-15
        0x00, 0xe6, 0x0f, 0x00,  # bytes 16-19
        0x06, 0x00, 0x04, 0x00,  # bytes 20-23
    )
    return build_packet(cmd_id=86, payload=payload, pkt_type=0x88, seq_id=seq_id)

def make_date_time_response(seq_id):
    now = datetime.datetime.now()
    payload = struct.pack('<BHHHHH', 
        0x00,
        now.year, 
        now.month, 
        now.day, 
        now.hour, 
        now.minute
    )
    return build_packet(cmd_id=70, payload=payload, pkt_type=PKT_TYPE_RESPONSE, seq_id=seq_id)
