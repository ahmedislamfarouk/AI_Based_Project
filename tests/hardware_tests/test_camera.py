import cv2
import time

def test_camera(index=0):
    print(f"--- Testing Camera index {index} ---")
    cap = cv2.VideoCapture(index)
    
    if not cap.isOpened():
        print(f"Error: Could not open camera {index}.")
        return

    print("Camera opened successfully. Press 'q' to quit.")
    
    start_time = time.time()
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame.")
            break
            
        cv2.imshow('Jetson Camera Test', frame)
        
        # Exit on 'q' or after 10 seconds automatically
        if cv2.waitKey(1) & 0xFF == ord('q') or (time.time() - start_time) > 10:
            break
            
    cap.release()
    cv2.destroyAllWindows()
    print("Camera test finished.")

if __name__ == "__main__":
    # Test video0 by default
    test_camera(0)
