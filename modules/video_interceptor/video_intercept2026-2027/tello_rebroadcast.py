import cv2
import socket
from djitellopy import Tello

PHONE_IP = "192.168.10.2" 
FORWARD_PORT = 11111

def main():
    #initialize the tello drone object
    drone = Tello()
    drone.connect()
    
    #turn on the drones video
    drone.streamon()
    
    # Setup a standard UDP socket to mirror the raw frames to your secondary device
    forward_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Establish the frame capture background thread
    frame_reader = drone.get_frame_read()
    
    print(f"\nLive stream active")
    print(f"Forwarding duplicate feed to {PHONE_IP}:{FORWARD_PORT}...")
    print("Press 'q' inside the video window to quit safely.\n")
    
    while True:
        #grab the current frame to display
        frame = frame_reader.frame
        #show the opencv window to show decoded images in infinite loop
        cv2.imshow("Tello Live PC Monitor", frame)
        
        # Extract and mirror raw payload chunks over the network to your phone
        # Note: If passing raw frame buffers, encode them to JPEG/H264 compressions
        _, encoded_frame = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        raw_bytes = encoded_frame.tobytes()
        
        # Chop larger frames into safe UDP packet sizes to prevent fragmentation drops
        packet_size = 1400
        for i in range(0, len(raw_bytes), packet_size):
            chunk = raw_bytes[i:i + packet_size]
            forward_socket.sendto(chunk, (PHONE_IP, FORWARD_PORT))
            
        #stop if q is pressed
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()
    drone.streamoff()
    forward_socket.close()

if __name__ == "__main__":
    main()
