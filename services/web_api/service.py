import os
import sys
import json
import math
import time
import asyncio
import threading
import subprocess
import tempfile
import io
import uuid
import base64
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import requests
from fastapi import FastAPI, WebSocket, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from modules.output.session_logger import SessionLogger

# Web API is lightweight: no ML deps. Face detection happens in face-analysis service.
# Display uses simple OpenCV Haar cascade for face boxes (fast, no GPU needed).

FACE_SERVICE_URL = os.getenv("FACE_SERVICE_URL", "http://127.0.0.1:8001")
VOICE_SERVICE_URL = os.getenv("VOICE_SERVICE_URL", "http://127.0.0.1:8002")
FUSION_SERVICE_URL = os.getenv("FUSION_SERVICE_URL", "http://127.0.0.1:8003")

app = FastAPI(title="Multimodal Emotion Monitor API", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SafeJSONResponse(JSONResponse):
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            default=lambda o: None if isinstance(o, float) and (math.isnan(o) or math.isinf(o)) else str(o),
        ).encode("utf-8")


def sanitize_for_json(obj):
    if obj is None:
        return None
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, np.floating):
        v = float(obj)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return sanitize_for_json(obj.tolist())
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(item) for item in obj]
    return obj


system_state = {
    "video_emotion": "Idle",
    "voice_emotion": "Idle",
    "biometric_data": "Idle",
    "stt_text": "",
    "llm_response": "Start a session to begin monitoring.",
    "distress": 0,
    "tts_audio_url": None,
    "tts_audio_mime": "audio/wav",
    "tts_audio_b64": None,
    "tts_generating": False,
}

TTS_OUTPUT_DIR = Path(os.path.join(os.path.dirname(__file__), "..", "data", "tts"))
TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
running = False
current_logger = None

latest_raw_frame = None
latest_display_frame = None
latest_annotated_frame = None
latest_annotated_time = 0.0

state_lock = threading.Lock()
frame_lock = threading.Lock()

CAMERA_SOURCE = os.getenv("CAMERA_SOURCE", "browser").strip().lower()
CAMERA_ID = int(os.getenv("CAMERA_ID", "0"))

cap = None
if CAMERA_SOURCE == "device":
    cap = cv2.VideoCapture(CAMERA_ID)
    if not cap.isOpened():
        print(f"[Startup] Warning: Camera index {CAMERA_ID} not available.")
        cap = None
else:
    print("[Startup] Browser camera mode enabled. Waiting for /api/browser-frame input.")

VOICE_BUFFER = bytearray()
VOICE_BUFFER_LOCK = threading.Lock()
VOICE_AUDIO_THRESHOLD = 16000 * 1  # 1 second of audio before sending


def _call_face_service(frame_bgr):
    """Send frame to face analysis microservice, return (annotated_frame, emotion)."""
    try:
        _, img_encoded = cv2.imencode('.jpg', frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        resp = requests.post(
            f"{FACE_SERVICE_URL}/analyze",
            files={"frame": ("face.jpg", io.BytesIO(img_encoded.tobytes()), "image/jpeg")},
            timeout=4
        )
        if resp.status_code == 200:
            data = resp.json()
            faces = data.get("faces", [])
            emotion = faces[0].get("emotion", "Neutral") if faces else "Neutral"
            b64_frame = data.get("annotated_frame_b64")
            if b64_frame:
                nparr = np.frombuffer(base64.b64decode(b64_frame), np.uint8)
                annotated = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                return annotated, emotion
        return None, None
    except Exception as e:
        print(f"[FaceService] Call failed: {e}")
        return None, None


def _call_voice_service(audio_bytes):
    """Send audio to voice analysis microservice, return {emotion, transcript, confidence}."""
    try:
        resp = requests.post(
            f"{VOICE_SERVICE_URL}/analyze",
            files={"audio": ("audio.raw", audio_bytes, "application/octet-stream")},
            timeout=6
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[VoiceService] Call failed: {e}")
    return {"emotion": "Neutral", "transcript": "", "confidence": 0}


def _call_fusion_service(face_emotion, voice_emotion, biometric, stt_text):
    """Send multimodal data to fusion LLM microservice."""
    try:
        resp = requests.post(
            f"{FUSION_SERVICE_URL}/fuse",
            json={"face_emotion": face_emotion, "voice_emotion": voice_emotion,
                  "biometric": biometric, "stt_text": stt_text},
            timeout=30
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[FusionService] Call failed: {e}")
    return {"distress": 50, "response": "I'm here with you."}


def _call_tts_service(text):
    """Generate TTS via fusion/tts endpoint, return base64 audio."""
    try:
        resp = requests.post(
            f"{FUSION_SERVICE_URL}/tts/generate",
            json={"text": text},
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("audio_base64"), data.get("mime_type", "audio/wav")
    except Exception as e:
        print(f"[TTSService] Call failed: {e}")
    return None, "audio/wav"


def _find_latest_tts_file():
    candidates = list(TTS_OUTPUT_DIR.glob("latest.*"))
    return candidates[0] if candidates else None


def _cleanup_old_tts(max_files=20):
    try:
        files = sorted(TTS_OUTPUT_DIR.glob("response_*"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[max_files:]:
            old.unlink(missing_ok=True)
    except Exception:
        pass


def get_state_payload():
    with state_lock:
        return {
            "running": running,
            "video_emotion": system_state["video_emotion"],
            "voice_emotion": system_state["voice_emotion"],
            "biometric_data": system_state["biometric_data"],
            "stt_text": system_state["stt_text"],
            "llm_response": system_state["llm_response"],
            "distress": system_state["distress"],
            "tts_audio_url": system_state["tts_audio_url"],
            "tts_audio_mime": system_state["tts_audio_mime"],
            "tts_audio_b64": system_state["tts_audio_b64"],
            "tts_generating": system_state["tts_generating"],
        }


def frame_reader():
    global latest_raw_frame
    while True:
        if CAMERA_SOURCE == "device" and cap and cap.isOpened():
            ret, frame = cap.read()
            if ret:
                frame = cv2.flip(frame, 1)
                with frame_lock:
                    latest_raw_frame = frame
        time.sleep(0.033)


def display_worker():
    global latest_display_frame, latest_annotated_frame, latest_annotated_time
    while True:
        if not running:
            time.sleep(0.1)
            continue

        now = time.time()
        with frame_lock:
            frame = latest_raw_frame.copy() if latest_raw_frame is not None else None
            annotated_frame = latest_annotated_frame
            annotated_age = now - latest_annotated_time if latest_annotated_frame is not None else 999

        if frame is not None:
            if annotated_frame is not None and annotated_age < 2.0:
                display = annotated_frame.copy()
            else:
                display = frame.copy()
                with state_lock:
                    emotion_text = system_state.get("video_emotion", "")
                if emotion_text:
                    cv2.putText(display, f"Emotion: {emotion_text}", (10, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

            with frame_lock:
                latest_display_frame = display

        time.sleep(0.033)


def video_worker():
    """Send frames to face analysis microservice every 1 second."""
    global system_state, latest_annotated_frame, latest_annotated_time
    last_analysis = 0
    while True:
        if not running:
            time.sleep(0.5)
            continue

        now = time.time()
        if now - last_analysis < 1.0:
            time.sleep(0.1)
            continue

        with frame_lock:
            frame = latest_raw_frame.copy() if latest_raw_frame is not None else None

        if frame is not None:
            annotated, emotion = _call_face_service(frame)
            if emotion:
                with state_lock:
                    system_state["video_emotion"] = emotion
                if annotated is not None:
                    with frame_lock:
                        latest_annotated_frame = annotated
                        latest_annotated_time = time.time()
            last_analysis = now
        time.sleep(0.1)


def voice_worker():
    """Send buffered audio to voice analysis microservice."""
    global system_state, VOICE_BUFFER
    while True:
        if not running:
            time.sleep(0.5)
            continue

        audio_data = None
        with VOICE_BUFFER_LOCK:
            if len(VOICE_BUFFER) >= VOICE_AUDIO_THRESHOLD:
                audio_data = bytes(VOICE_BUFFER)
                VOICE_BUFFER = bytearray()

        if audio_data:
            result = _call_voice_service(audio_data)
            if result:
                with state_lock:
                    system_state["voice_emotion"] = result.get("emotion", "Neutral")
                    transcript = result.get("transcript", "")
                    if transcript:
                        system_state["stt_text"] = transcript

        time.sleep(1.0)


def biometric_worker():
    """Mock biometrics (no hardware in web-api container)."""
    global system_state
    hr = 72.0
    spo2 = 98.0
    while True:
        if not running:
            time.sleep(0.5)
            continue
        hr += np.random.normal(0, 1)
        spo2 += np.random.normal(0, 0.2)
        hr = float(np.clip(hr, 50, 150))
        spo2 = float(np.clip(spo2, 85, 100))
        with state_lock:
            system_state["biometric_data"] = f"HR: {hr:.1f}, SpO2: {spo2:.1f}%"
        time.sleep(2.0)


def ai_fusion_worker():
    global system_state, current_logger
    last_recommendation = ""
    last_tts_time = 0
    tts_repeat_interval = 5
    tts_distress_threshold = int(os.getenv("TTS_DISTRESS_THRESHOLD", "0"))
    while True:
        if not running:
            time.sleep(1)
            continue
        try:
            with state_lock:
                face_emotion = system_state["video_emotion"]
                voice_emotion = system_state["voice_emotion"]
                biometric = system_state["biometric_data"]
                stt_text = system_state["stt_text"]

            result = _call_fusion_service(face_emotion, voice_emotion, biometric, stt_text)

            distress = result.get("distress", 0)
            response = result.get("response", "I'm here with you.")

            with state_lock:
                system_state["llm_response"] = response
                system_state["distress"] = distress

            now = time.time()
            response_changed = response != last_recommendation
            repeat_due = (now - last_tts_time) > tts_repeat_interval

            if response and distress >= tts_distress_threshold and (response_changed or repeat_due):
                with state_lock:
                    system_state["tts_generating"] = True
                    system_state["tts_audio_url"] = None
                    system_state["tts_audio_b64"] = None
                print(f"[AI Fusion] Triggering TTS for distress={distress}: {response[:80]}...")
                audio_b64, mime = _call_tts_service(response)
                if audio_b64:
                    with state_lock:
                        system_state["tts_audio_b64"] = audio_b64
                        system_state["tts_audio_mime"] = mime
                        system_state["tts_audio_url"] = f"/api/tts/latest?t={int(time.time())}"
                with state_lock:
                    system_state["tts_generating"] = False
                last_recommendation = response
                last_tts_time = now

            if current_logger:
                current_logger.log_event(system_state)

        except Exception as e:
            print(f"[AI Fusion] Error: {e}")
            import traceback
            traceback.print_exc()
        time.sleep(2)


for target in [frame_reader, display_worker, video_worker, voice_worker, biometric_worker, ai_fusion_worker]:
    threading.Thread(target=target, daemon=True).start()


# ─── API Endpoints ──────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    return FileResponse(os.path.join("static", "index.html"))


@app.post("/api/start")
def start_session():
    global running, current_logger
    if running:
        return {"status": "already_running"}
    running = True
    current_logger = SessionLogger()
    with state_lock:
        system_state["video_emotion"] = "Starting..."
        system_state["voice_emotion"] = "Starting..."
        system_state["biometric_data"] = "Starting..."
        system_state["llm_response"] = "Initializing..."
        system_state["distress"] = 0
    return {"status": "started"}


@app.post("/api/stop")
def stop_session():
    global running
    running = False
    with state_lock:
        system_state["video_emotion"] = "Idle"
        system_state["voice_emotion"] = "Idle"
        system_state["biometric_data"] = "Idle"
        system_state["llm_response"] = "Session stopped."
        system_state["distress"] = 0
        system_state["stt_text"] = ""
        system_state["tts_audio_url"] = None
        system_state["tts_audio_b64"] = None
        system_state["tts_generating"] = False
    return {"status": "stopped"}


@app.get("/api/tts/latest")
def get_latest_tts():
    latest = _find_latest_tts_file()
    if latest is None or not latest.exists():
        return JSONResponse(content={"status": "not_found"}, status_code=404)
    mime = "audio/wav"
    if latest.suffix == ".mp3":
        mime = "audio/mpeg"
    return FileResponse(str(latest), media_type=mime)


@app.post("/api/browser-frame")
async def ingest_browser_frame(frame: UploadFile = File(...)):
    global latest_raw_frame
    content = await frame.read()
    if not content:
        return {"status": "empty_frame"}

    np_arr = np.frombuffer(content, np.uint8)
    decoded = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if decoded is None:
        return {"status": "invalid_frame"}

    decoded = cv2.flip(decoded, 1)
    with frame_lock:
        latest_raw_frame = decoded
    return {"status": "ok"}


@app.post("/api/browser-audio")
async def ingest_browser_audio(audio: UploadFile = File(...)):
    global VOICE_BUFFER
    content = await audio.read()
    if not content:
        return {"status": "empty_audio"}

    content_type = audio.content_type or ""
    tmp_path = None

    if "webm" in content_type or "ogg" in content_type or "mp4" in content_type:
        try:
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            out_path = tmp_path + ".raw"
            cmd = [
                "ffmpeg", "-y", "-i", tmp_path,
                "-f", "s16le", "-acodec", "pcm_s16le",
                "-ar", "16000", "-ac", "1",
                out_path
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            if result.returncode == 0 and os.path.exists(out_path):
                with open(out_path, "rb") as f:
                    raw_data = f.read()
                with VOICE_BUFFER_LOCK:
                    VOICE_BUFFER.extend(raw_data)
                try:
                    os.remove(out_path)
                except OSError:
                    pass
        except Exception as e:
            print(f"[Audio] FFmpeg decode error: {e}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
    elif "wav" in content_type:
        with VOICE_BUFFER_LOCK:
            VOICE_BUFFER.extend(content)
    else:
        with VOICE_BUFFER_LOCK:
            VOICE_BUFFER.extend(content)

    return {"status": "ok"}


def generate_mjpeg():
    blank = np.zeros((360, 480, 3), dtype=np.uint8)
    blank[:] = (5, 5, 6)
    cv2.putText(blank, "Start a session to begin", (60, 180),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 100, 110), 1)
    cv2.putText(blank, "Camera feed will appear here", (50, 220),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (70, 70, 80), 1)
    _, blank_jpg = cv2.imencode('.jpg', blank, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    blank_bytes = blank_jpg.tobytes()

    while True:
        with frame_lock:
            frame = latest_display_frame if latest_display_frame is not None else latest_raw_frame
        if frame is not None:
            ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        else:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + blank_bytes + b'\r\n')
        time.sleep(0.033)


@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generate_mjpeg(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            payload = await asyncio.to_thread(get_state_payload)
            await websocket.send_json(sanitize_for_json(payload))
            await asyncio.sleep(1)
    except Exception:
        pass


@app.get("/api/history")
def get_history():
    import glob as glob_module
    list_of_files = glob_module.glob('data/sessions/*.csv')
    if not list_of_files:
        return []
    latest = max(list_of_files, key=os.path.getctime)
    try:
        import pandas as pd
        df = pd.read_csv(latest)
        df = df.tail(100)
        df = df.where(pd.notnull(df), None)
        df = df.replace([float('inf'), float('-inf')], None)
        records = df.to_dict(orient='records')
        return SafeJSONResponse(content=sanitize_for_json(records))
    except Exception as e:
        return SafeJSONResponse(content={"error": str(e)})


@app.on_event("shutdown")
def shutdown_event():
    if cap and cap.isOpened():
        cap.release()
    cv2.destroyAllWindows()


static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
