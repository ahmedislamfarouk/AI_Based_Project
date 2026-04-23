import cv2
import os
import io
import subprocess
import tempfile
import requests
import numpy as np
from collections import Counter

FACE_ANALYSIS_URL = os.environ.get("FACE_ANALYSIS_URL", "http://127.0.0.1:8001")


class VideoSessionProcessor:
    def __init__(self):
        self._deepface_available = None
        self._ser = None
        self._stt = None
        self._feature_extractor = None
        self._face_service_available = None
        self._face_service_check_time = 0

    def _check_face_service(self):
        now = __import__('time').time()
        if self._face_service_available is not None and (now - self._face_service_check_time) < 30:
            return self._face_service_available
        try:
            resp = requests.get(f"{FACE_ANALYSIS_URL}/health", timeout=2)
            if resp.status_code == 200:
                self._face_service_available = True
                self._face_service_check_time = now
                return True
        except Exception:
            pass
        self._face_service_available = False
        self._face_service_check_time = now
        return False

    def _init_deepface(self):
        if self._deepface_available is None:
            try:
                from deepface import DeepFace
                self._deepface_available = True
                print("[VideoProcessor] DeepFace available.")
            except Exception as e:
                print(f"[VideoProcessor] DeepFace unavailable: {e}")
                self._deepface_available = False
        return self._deepface_available

    def _init_ser(self):
        if self._ser is None:
            try:
                from modules.voice.ser_model import SERInference
                self._ser = SERInference()
            except Exception as e:
                print(f"[VideoProcessor] SER init failed: {e}")
                self._ser = False
        return self._ser if self._ser is not False else None

    def _init_stt(self):
        if self._stt is None:
            try:
                from modules.voice.stt_engine import STTEngine
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
                self._stt = STTEngine(model_size="tiny", device=device)
            except Exception as e:
                print(f"[VideoProcessor] STT init failed: {e}")
                self._stt = False
        return self._stt if self._stt is not False else None

    def extract_audio_from_video(self, video_path, output_path=None):
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg audio extraction failed: {result.stderr.decode()[:500]}")
        return output_path

    def extract_frames(self, video_path, interval_sec=2.0):
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 25.0
        interval_frames = int(fps * interval_sec)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        frames = []
        frame_indices = []
        idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if idx % interval_frames == 0:
                frames.append(frame)
                frame_indices.append(idx)
            idx += 1
        cap.release()
        return frames, frame_indices, fps

    def analyze_fer(self, frames):
        valid_emotions = []
        if not frames:
            return {"dominant_emotion": "Neutral", "emotion_counts": {}, "total_frames": 0}

        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        min_face_ratio = 0.05

        # Tier 1: Try external face analysis microservice (MediaPipe+DeepFace on host GPU)
        if self._check_face_service():
            for i, frame in enumerate(frames):
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.3, 5)
                if len(faces) == 0:
                    continue
                (x, y, w, h) = max(faces, key=lambda f: f[2] * f[3])
                if (w / frame.shape[1]) < min_face_ratio:
                    continue
                margin = 30
                x1, y1 = max(x - margin, 0), max(y - margin, 0)
                x2 = min(x + w + margin, frame.shape[1])
                y2 = min(y + h + margin, frame.shape[0])
                face_crop = frame[y1:y2, x1:x2]
                try:
                    _, img_encoded = cv2.imencode('.jpg', face_crop, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                    resp = requests.post(
                        f"{FACE_ANALYSIS_URL}/analyze",
                        files={"frame": ("face.jpg", io.BytesIO(img_encoded.tobytes()), "image/jpeg")},
                        timeout=3
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        face_results = data.get("faces", [])
                        if face_results:
                            emotion = face_results[0].get("emotion", "Neutral")
                            valid_emotions.append(emotion.capitalize() if isinstance(emotion, str) else emotion)
                            continue
                except Exception:
                    pass
                # If microservice call failed for this frame, fall through to local
                break

            if valid_emotions:
                print(f"[FER] Face analysis service: {len(valid_emotions)}/{len(frames)} frames analyzed")
                counter = Counter(valid_emotions)
                dominant = counter.most_common(1)[0][0]
                counts = {k: v for k, v in counter.most_common()}
                return {
                    "dominant_emotion": dominant,
                    "emotion_counts": counts,
                    "total_frames": len(frames)
                }

        # Tier 2: Local DeepFace (skip detector, then opencv fallback)
        if self._init_deepface():
            from deepface import DeepFace
            for i, frame in enumerate(frames):
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.3, 5)
                if len(faces) == 0:
                    continue

                (x, y, w, h) = max(faces, key=lambda f: f[2] * f[3])
                if (w / frame.shape[1]) < min_face_ratio:
                    continue

                margin = 30
                x1 = max(x - margin, 0)
                y1 = max(y - margin, 0)
                x2 = min(x + w + margin, frame.shape[1])
                y2 = min(y + h + margin, frame.shape[0])
                face_crop = frame[y1:y2, x1:x2]

                try:
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
                        valid_emotions.append(emotion.capitalize())
                except Exception:
                    try:
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
                            valid_emotions.append(emotion.capitalize())
                    except Exception:
                        pass

                if (i + 1) % 10 == 0:
                    print(f"[FER] Processed {i+1}/{len(frames)} frames, {len(valid_emotions)} with face detected")
        else:
            # Tier 3: Haar cascade heuristic
            for frame in frames:
                try:
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
                    if len(faces) > 0:
                        ratio = faces[0][2] / frame.shape[1]
                        valid_emotions.append("Anxious" if ratio > 0.4 else "Calm")
                except Exception:
                    pass

        if not valid_emotions:
            return {"dominant_emotion": "Neutral", "emotion_counts": {}, "total_frames": len(frames)}

        counter = Counter(valid_emotions)
        dominant = counter.most_common(1)[0][0]
        counts = {k: v for k, v in counter.most_common()}
        return {
            "dominant_emotion": dominant,
            "emotion_counts": counts,
            "total_frames": len(frames)
        }

    def analyze_ser(self, audio_path):
        ser = self._init_ser()
        if ser is None:
            return {"dominant_emotion": "Unavailable", "emotion_counts": {}}

        try:
            from modules.voice.ser_model import NUM_SAMPLES
            import soundfile as sf
            waveform, sr = sf.read(audio_path)
            if len(waveform.shape) > 1:
                waveform = waveform.mean(axis=1)
            waveform = waveform.astype(np.float32)

            if sr != 16000:
                import torchaudio
                resampler = torchaudio.transforms.Resample(sr, 16000)
                waveform = resampler(torch.from_numpy(waveform)).numpy()
                sr = 16000

            dominant, emotion_weights, avg_conf = ser.predict_batch(
                waveform, sr=sr, min_confidence=0.30
            )

            total = sum(emotion_weights.values()) if emotion_weights else 1
            counts = {k: round(v, 2) for k, v in sorted(
                emotion_weights.items(), key=lambda x: x[1], reverse=True
            )} if emotion_weights else {}

            return {
                "dominant_emotion": dominant,
                "emotion_counts": counts
            }
        except Exception as e:
            print(f"[VideoProcessor] SER analysis error: {e}")
            return {"dominant_emotion": "Error", "emotion_counts": {}}

    def transcribe_audio(self, audio_path):
        stt = self._init_stt()
        if stt is None:
            return ""

        try:
            import soundfile as sf
            import torch
            waveform, sr = sf.read(audio_path)
            if len(waveform.shape) > 1:
                waveform = waveform.mean(axis=1)
            waveform = waveform.astype(np.float32)

            chunk_duration = 30
            chunk_size = int(sr * chunk_duration)
            segments_text = []

            for i in range(0, len(waveform), chunk_size):
                chunk = waveform[i:i + chunk_size]
                if len(chunk) < sr:
                    continue
                text = stt.transcribe(chunk, sr=sr)
                if text:
                    segments_text.append(text)

            if not segments_text and len(waveform) >= sr:
                text = stt.transcribe(waveform, sr=sr)
                if text:
                    segments_text.append(text)

            return " ".join(segments_text).strip()
        except Exception as e:
            print(f"[VideoProcessor] STT error: {e}")
            return ""

    def process_video_session(self, video_path):
        results = {
            "fer_emotion": "Neutral",
            "fer_emotion_counts": {},
            "ser_emotion": "Neutral",
            "ser_emotion_counts": {},
            "stt_text": "",
            "total_frames_analyzed": 0,
            "status": "processing"
        }

        try:
            print("[VideoProcessor] Extracting audio...")
            audio_path = self.extract_audio_from_video(video_path)

            print("[VideoProcessor] Extracting frames...")
            frames, frame_indices, fps = self.extract_frames(video_path, interval_sec=2.0)
            results["total_frames_analyzed"] = len(frames)

            print(f"[VideoProcessor] Running FER on {len(frames)} frames...")
            fer_result = self.analyze_fer(frames)
            results["fer_emotion"] = fer_result["dominant_emotion"]
            results["fer_emotion_counts"] = fer_result["emotion_counts"]

            print("[VideoProcessor] Running SER on audio...")
            ser_result = self.analyze_ser(audio_path)
            results["ser_emotion"] = ser_result["dominant_emotion"]
            results["ser_emotion_counts"] = ser_result["emotion_counts"]

            print("[VideoProcessor] Running STT on audio...")
            stt_text = self.transcribe_audio(audio_path)
            results["stt_text"] = stt_text

            try:
                os.remove(audio_path)
            except OSError:
                pass

            results["status"] = "completed"
        except Exception as e:
            print(f"[VideoProcessor] Error: {e}")
            results["status"] = f"error: {str(e)}"

        return results