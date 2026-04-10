import cv2
import time

class VideoEmotionAnalyzer:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.last_emotion = "Neutral"

    def analyze_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return "No Camera Found"

        # Flip frame: 0 = vertical, 1 = horizontal, -1 = both
        frame = cv2.flip(frame, -1)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)

        if len(faces) > 0:
            (x, y, w, h) = faces[0]
            # Heuristic: Large face (close to camera) + movement = Higher arousal/distress
            face_ratio = w / frame.shape[1]
            if face_ratio > 0.4:
                self.last_emotion = "Anxious/High Arousal (Close)"
            else:
                self.last_emotion = "Calm/Attentive"
        else:
            self.last_emotion = "No Face Detected"

        return self.last_emotion

    def close(self):
        self.cap.release()

if __name__ == "__main__":
    v_analyzer = VideoEmotionAnalyzer()
    try:
        while True:
            emotion = v_analyzer.analyze_frame()
            print(f"Video Emotion: {emotion}")
            time.sleep(0.5)
    except KeyboardInterrupt:
        v_analyzer.close()
