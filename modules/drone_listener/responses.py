import datetime
import struct
from protocol import build_packet, PKT_TYPE_RESPONSE

def make_conn_ack():
    return b"conn_ack:g+"

def make_stick_ack(seq_id):
    return build_packet(cmd_id=80, payload=b'', pkt_type=PKT_TYPE_RESPONSE, seq_id=seq_id)

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
