import cv2
import time

def gstreamer_pipeline(
    sensor_id=0,
    capture_width=1280,
    capture_height=720,
    display_width=1280,
    display_height=720,
    framerate=30,
    flip_method=0,
):
    return (
        "nvarguscamerasrc sensor-id=%d ! "
        "video/x-raw(memory:NVMM), "
        "width=(int)%d, height=(int)%d, "
        "format=(string)NV12, framerate=(fraction)%d/1 ! "
        "nvvidconv flip-method=%d ! "
        "video/x-raw, width=(int)%d, height=(int)%d, format=(string)BGRx ! "
        "videoconvert ! "
        "video/x-raw, format=(string)BGR ! appsink"
        % (
            sensor_id,
            capture_width,
            capture_height,
            framerate,
            flip_method,
            display_width,
            display_height,
        )
    )

def test_camera(index=0):
    print(f"--- Testing Camera index {index} ---")
    
    # Try GStreamer pipeline first if on Jetson and it might be a CSI camera
    # If this fails or index is not 0, we fall back to simple index
    pipeline = gstreamer_pipeline(sensor_id=index)
    print("Trying CSI camera pipeline...")
    cap = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
    
    if not cap.isOpened():
        print("CSI pipeline failed or not available. Falling back to simple index...")
        cap = cv2.VideoCapture(index)

    if not cap.isOpened():
        print(f"Error: Could not open camera {index} with any method.")
        return

    print("Camera opened successfully. Press 'q' to quit.")
    
    start_time = time.time()
    num_frames = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame. The camera might be in use or disconnected.")
            break
        
        num_frames += 1
        cv2.imshow('Jetson Camera Test', frame)
        
        # Exit on 'q' or after 10 seconds automatically
        if cv2.waitKey(1) & 0xFF == ord('q') or (time.time() - start_time) > 10:
            break
            
    cap.release()
    cv2.destroyAllWindows()
    print(f"Camera test finished. Total frames captured: {num_frames}")

if __name__ == "__main__":
    # Test video0 by default
    test_camera(0)
