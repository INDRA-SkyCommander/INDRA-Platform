import socket
import threading
import time

VIDEO_PORT = 11111

class TelloVideoStreamer:
    def __init__(self, video_file: str, phone_ip: str):
        self.video_file = video_file
        self.phone_ip = phone_ip
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._stop_event = threading.Event()
        self._thread = None
        self.streaming = False

    def start(self):
        if self.streaming:
            print("[!] Video stream already running.")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()
        self.streaming = True
        print(f"[*] Video stream started -> {self.phone_ip}:{VIDEO_PORT}")

    def stop(self):
        self._stop_event.set()
        self.streaming = False
        print("[*] Video stream stopped.")

    def _packetize(self, nal_Data: bytes, seq: int):

        MAX_PAYLOAD = 1460
        chunks = [nal_Data[i:i + MAX_PAYLOAD] for i in range(0, len(nal_Data), MAX_PAYLOAD)]
        packets = []
        for i, chunk in enumerate(chunks):
            is_last = (i == len(chunks) - 1)
            subseq = i & 0x7F
            if is_last:
                subseq |= 0x80 # mark last fragment
            header = bytes([seq & 0xFF, subseq])
            packets.append(header + chunk)
        return packets
    
    def _read_nal_units(self, data: bytes):
        # Splits raw H.264 byte stream into NAL units. 

        START_4 = b'\x00\x00\x00\x01'
        START_3 = b'\x00\x00\x01'

        i = 0
        nal_start = None

        while i < len(data):
            if data[i:i+4] == START_4:
                if nal_start is not None:
                    yield data[nal_start:i]
                nal_start = i + 4
                i += 4
            elif data[i:i+3] == START_3:
                if nal_start is not None:
                    yield data[nal_start:i]
                nal_start = i + 3
                i += 3
            else:
                i += 1

        # Yield the last NAL unit if we reached the end of the data
        if nal_start is not None:
            yield data[nal_start:]
    
    def _stream_loop(self):
        seq = 0

        # Read the entire file once
        try: 
            with open(self.video_file, 'rb') as f:
                raw_data = f.read()
        except Exception as e:
            print(f"[!] Failed to read video file: {e}")
            return

        print(f"[*] Loaded {len(raw_data)} bytes from {self.video_file}")

        # Extract NAL units from the raw data
        while not self._stop_event.is_set():
            for nal in self._read_nal_units(raw_data):
                if self._stop_event.is_set():
                    break
                
                packets = self._packetize(nal, seq)
                for pkt in packets:
                    if self._stop_event.is_set():
                        break
                    try:
                        self.sock.sendto(pkt, (self.phone_ip, VIDEO_PORT))
                    except Exception as e:
                        print(f"[!] Video send error: {e}")
                
                seq = (seq + 1) & 0xFF
                time.sleep(0.033) # ~30fps