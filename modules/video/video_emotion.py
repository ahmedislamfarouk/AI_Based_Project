import cv2
import io
import time
import threading
import requests
import os
import numpy as np

FACE_ANALYSIS_URL = os.environ.get("FACE_ANALYSIS_URL", "http://127.0.0.1:8001")
_REQUEST_TIMEOUT = 2


class VideoEmotionAnalyzer:
    def __init__(self, cap=None, open_default=True, fast_mode=False):
        self.own_cap = cap is None and open_default
        self.cap = cap if cap is not None else (cv2.VideoCapture(0) if open_default else None)
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.last_emotion = "Neutral"
        self.fast_mode = fast_mode
        self._deepface_available = None
        self._last_deepface_time = 0
        self._deepface_interval = 2.0
        self._deepface_lock = threading.Lock()
        self._face_service_available = None
        self._face_service_check_time = 0
        self._face_service_interval = 10

    def _check_face_service(self):
        now = time.time()
        if self._face_service_available is not None and (now - self._face_service_check_time) < self._face_service_interval:
            return self._face_service_available
        try:
            resp = requests.get(f"{FACE_ANALYSIS_URL}/health", timeout=1)
            if resp.status_code == 200:
                self._face_service_available = True
                self._face_service_check_time = now
                return True
        except Exception:
            pass
        self._face_service_available = False
        self._face_service_check_time = now
        return False

    def _check_deepface(self):
        if self._deepface_available is None:
            try:
                from deepface import DeepFace
                self._deepface_available = True
                print("[VideoEmotion] DeepFace available for emotion detection.")
            except Exception as e:
                print(f"[VideoEmotion] DeepFace unavailable, using heuristic fallback: {e}")
                self._deepface_available = False
        return self._deepface_available

    def analyze_frame(self):
        if self.cap is None or not self.cap.isOpened():
            return "No Camera Found"
        ret, frame = self.cap.read()
        if not ret:
            return "No Camera Found"

        frame = cv2.flip(frame, -1)
        return self._process_frame(frame)

    def analyze_frame_given(self, frame):
        if frame is None:
            return "No Frame"
        return self._process_frame(frame)

    def _process_frame(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)

        if len(faces) == 0:
            self.last_emotion = "No Face Detected"
            return self.last_emotion

        (x, y, w, h) = max(faces, key=lambda f: f[2] * f[3])
        min_face_ratio = 0.05
        if (w / frame.shape[1]) < min_face_ratio:
            self.last_emotion = "No Face Detected"
            return self.last_emotion

        if self.fast_mode:
            face_ratio = w / frame.shape[1]
            self.last_emotion = "Anxious" if face_ratio > 0.4 else "Calm"
            return self.last_emotion

        margin = 30
        x1 = max(x - margin, 0)
        y1 = max(y - margin, 0)
        x2 = min(x + w + margin, frame.shape[1])
        y2 = min(y + h + margin, frame.shape[0])
        face_crop = frame[y1:y2, x1:x2]

        # Tier 1: External face analysis microservice (best: MediaPipe + DeepFace)
        if self._check_face_service():
            try:
                _, img_encoded = cv2.imencode('.jpg', face_crop, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                resp = requests.post(
                    f"{FACE_ANALYSIS_URL}/analyze",
                    files={"frame": ("face.jpg", io.BytesIO(img_encoded.tobytes()), "image/jpeg")},
                    timeout=_REQUEST_TIMEOUT
                )
                if resp.status_code == 200:
                    data = resp.json()
                    face_results = data.get("faces", [])
                    if face_results:
                        emotion = face_results[0].get("emotion", "Neutral")
                        self.last_emotion = emotion.capitalize() if isinstance(emotion, str) else emotion
                        return self.last_emotion
            except Exception:
                pass

        # Tier 2: Local DeepFace (mediapipe detector, then skip, then opencv)
        now = time.time()
        if self._check_deepface():
            with self._deepface_lock:
                if now - self._last_deepface_time >= self._deepface_interval:
                    try:
                        from deepface import DeepFace
                        result = DeepFace.analyze(
                            face_crop, actions=['emotion'],
                            enforce_detection=False,
                            detector_backend='skip',
                            silent=True
                        )
                        emotion = result[0]['dominant_emotion']
                        probs = result[0].get('emotion', {})
                        max_prob = max(probs.values()) if probs else 0
                        if max_prob >= 0.25:
                            self.last_emotion = emotion.capitalize()
                            self._last_deepface_time = now
                            return self.last_emotion
                    except Exception:
                        try:
                            from deepface import DeepFace
                            result = DeepFace.analyze(
                                face_crop, actions=['emotion'],
                                enforce_detection=False,
                                detector_backend='opencv',
                                silent=True
                            )
                            emotion = result[0]['dominant_emotion']
                            probs = result[0].get('emotion', {})
                            max_prob = max(probs.values()) if probs else 0
                            if max_prob >= 0.25:
                                self.last_emotion = emotion.capitalize()
                                self._last_deepface_time = now
                                return self.last_emotion
                        except Exception:
                            pass

        # Tier 3: Haar heuristic fallback
        face_ratio = w / frame.shape[1]
        self.last_emotion = "Anxious" if face_ratio > 0.4 else "Calm"
        return self.last_emotion

    def close(self):
        if self.own_cap and self.cap:
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