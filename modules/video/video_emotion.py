import cv2
import numpy as np
import time

class VideoEmotionAnalyzer:
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.cap = cv2.VideoCapture(0) # Kit camera is usually 0
        self.last_detection = "Neutral"

    def analyze_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return "No Video"
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
        
        if len(faces) > 0:
            # Mock analysis: If more than 1 face or face is close, assume movement/distress
            # In production, replace with a pre-trained CNN (e.g., DeepFace)
            self.last_detection = "Focused/Distressed" if len(faces) > 1 else "Interested"
        else:
            self.last_detection = "Bored/Not Present"
            
        return self.last_detection

    def release(self):
        self.cap.release()

if __name__ == "__main__":
    analyzer = VideoEmotionAnalyzer()
    try:
        while True:
            emotion = analyzer.analyze_frame()
            print(f"Video Emotion: {emotion}")
            time.sleep(1)
    except KeyboardInterrupt:
        analyzer.release()
