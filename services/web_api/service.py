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
    "stt_text": "",
    "llm_response": "Start a session to begin monitoring.",
    "distress": 0,
    "tts_audio_url": None,
    "tts_audio_mime": "audio/wav",
    "tts_audio_b64": None,
    "tts_generating": False,
    "conversation_history": [],
    "health_face": "off",
    "health_voice": "off",
    "health_llm": "off",
}

TTS_OUTPUT_DIR = Path(os.path.join(os.path.dirname(__file__), "..", "data", "tts"))
TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
running = False
current_logger = None

latest_raw_frame = None
raw_frame_version = 0

state_lock = threading.Lock()
frame_lock = threading.Lock()

CAMERA_SOURCE = os.getenv("CAMERA_SOURCE", "browser").strip().lower()
CAMERA_ID = int(os.getenv("CAMERA_ID", "0"))

cap = None
if CAMERA_SOURCE == "device":
    cap = cv2.VideoCapture(CAMERA_ID)
    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 15)
    else:
        print(f"[Startup] Warning: Camera index {CAMERA_ID} not available.")
        cap = None
else:
    print("[Startup] Browser camera mode enabled. Waiting for /api/browser-frame input.")

VOICE_BUFFER = bytearray()
VOICE_BUFFER_LOCK = threading.Lock()
VOICE_AUDIO_THRESHOLD = 32000  # 1 second of audio (16kHz 16-bit = 32000 bytes)
AUDIO_RECORDING_ACTIVE = False
AUDIO_RECORDING_LOCK = threading.Lock()


def _call_face_service(frame_bgr):
    try:
        # Resize for faster transfer/processing
        h, w = frame_bgr.shape[:2]
        max_dim = 320
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            frame_bgr = cv2.resize(frame_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        _, img_encoded = cv2.imencode('.jpg', frame_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
        resp = requests.post(
            f"{FACE_SERVICE_URL}/analyze",
            files={"frame": ("face.jpg", io.BytesIO(img_encoded.tobytes()), "image/jpeg")},
            timeout=3
        )
        if resp.status_code == 200:
            data = resp.json()
            faces = data.get("faces", [])
            return faces[0].get("emotion", "Neutral") if faces else None
        return None
    except Exception as e:
        print(f"[FaceService] Call failed: {e}")
        return None


def _call_voice_service(audio_bytes):
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


def _call_fusion_service(face_emotion, voice_emotion, biometric, stt_text, history=None):
    try:
        payload = {"face_emotion": face_emotion, "voice_emotion": voice_emotion,
                   "biometric": biometric, "stt_text": stt_text}
        if history:
            payload["history"] = history
        resp = requests.post(
            f"{FUSION_SERVICE_URL}/fuse",
            json=payload,
            timeout=30
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[FusionService] Call failed: {e}")
    return {"distress": 50, "response": "I'm here with you."}


def _call_tts_service(text):
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
            "stt_text": system_state["stt_text"],
            "llm_response": system_state["llm_response"],
            "distress": system_state["distress"],
            "tts_audio_url": system_state["tts_audio_url"],
            "tts_audio_mime": system_state["tts_audio_mime"],
            "tts_audio_b64": system_state["tts_audio_b64"],
            "tts_generating": system_state["tts_generating"],
            "health_face": system_state["health_face"],
            "health_voice": system_state["health_voice"],
            "health_llm": system_state["health_llm"],
        }


def frame_reader():
    global latest_raw_frame, raw_frame_version
    while True:
        if CAMERA_SOURCE == "device" and cap and cap.isOpened():
            ret, frame = cap.read()
            if ret:
                frame = cv2.flip(frame, 1)
                with frame_lock:
                    latest_raw_frame = frame
                    raw_frame_version += 1
        time.sleep(0.066)


def video_worker():
    global system_state
    last_analysis = 0
    while True:
        if not running:
            time.sleep(0.5)
            continue

        now = time.time()
        if now - last_analysis < 0.3:
            time.sleep(0.05)
            continue

        with frame_lock:
            frame = latest_raw_frame.copy() if latest_raw_frame is not None else None

        if frame is not None:
            emotion = _call_face_service(frame)
            if emotion:
                with state_lock:
                    system_state["video_emotion"] = emotion
            last_analysis = now
        time.sleep(0.05)


def voice_worker():
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
                        current = system_state.get("stt_text", "")
                        combined = (current + " " + transcript).strip()
                        system_state["stt_text"] = combined[-500:] if len(combined) > 500 else combined
                        print(f"[STT] +{len(transcript)} chars: {transcript[:80]}")

        time.sleep(0.3)


def health_watcher():
    """Periodically check service health."""
    global system_state
    while True:
        try:
            fr = requests.get(f"{FACE_SERVICE_URL}/health", timeout=2)
            with state_lock:
                system_state["health_face"] = "ok" if fr.status_code == 200 else "err"
        except Exception:
            with state_lock:
                system_state["health_face"] = "off"
        try:
            vr = requests.get(f"{VOICE_SERVICE_URL}/health", timeout=2)
            with state_lock:
                system_state["health_voice"] = "ok" if vr.status_code == 200 else "err"
        except Exception:
            with state_lock:
                system_state["health_voice"] = "off"
        try:
            lr = requests.get(f"{FUSION_SERVICE_URL}/health", timeout=2)
            with state_lock:
                system_state["health_llm"] = "ok" if lr.status_code == 200 else "err"
        except Exception:
            with state_lock:
                system_state["health_llm"] = "off"
        time.sleep(5)


for target in [frame_reader, video_worker, voice_worker, health_watcher]:
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
        system_state["llm_response"] = "Initializing..."
        system_state["distress"] = 0
        system_state["conversation_history"] = []
    return {"status": "started"}


@app.post("/api/stop")
def stop_session():
    global running
    running = False
    with state_lock:
        system_state["video_emotion"] = "Idle"
        system_state["voice_emotion"] = "Idle"
        system_state["llm_response"] = "Session stopped."
        system_state["distress"] = 0
        system_state["stt_text"] = ""
        system_state["tts_audio_url"] = None
        system_state["tts_audio_b64"] = None
        system_state["tts_generating"] = False
        system_state["conversation_history"] = []
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
    global latest_raw_frame, raw_frame_version
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
        raw_frame_version += 1
    return {"status": "ok"}


@app.post("/api/audio/start")
def start_audio_recording():
    global AUDIO_RECORDING_ACTIVE
    with AUDIO_RECORDING_LOCK:
        AUDIO_RECORDING_ACTIVE = True
    with VOICE_BUFFER_LOCK:
        VOICE_BUFFER.clear()
    with state_lock:
        system_state["stt_text"] = ""
    return {"status": "recording_started"}


@app.post("/api/audio/stop")
def stop_audio_recording():
    global AUDIO_RECORDING_ACTIVE, VOICE_BUFFER
    with AUDIO_RECORDING_LOCK:
        AUDIO_RECORDING_ACTIVE = False
    # Process any remaining audio before clearing
    with VOICE_BUFFER_LOCK:
        remaining = bytes(VOICE_BUFFER) if len(VOICE_BUFFER) > 8000 else None
        VOICE_BUFFER.clear()
    if remaining:
        try:
            result = _call_voice_service(remaining)
            if result:
                with state_lock:
                    transcript = result.get("transcript", "")
                    if transcript:
                        current = system_state.get("stt_text", "")
                        combined = (current + " " + transcript).strip()
                        system_state["stt_text"] = combined[-500:] if len(combined) > 500 else combined
        except Exception as e:
            print(f"[Audio] Final chunk processing error: {e}")
    return {"status": "recording_stopped"}


@app.post("/api/stt/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Full coordinated pipeline: STT + voice emotion + fusion + TTS in one shot."""
    content = await audio.read()
    if not content:
        return {"transcript": ""}

    content_type = audio.content_type or ""
    raw_data = None

    if "webm" in content_type or "ogg" in content_type or "mp4" in content_type:
        try:
            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            out_path = tmp_path + ".raw"
            cmd = ["ffmpeg", "-y", "-i", tmp_path,
                   "-f", "s16le", "-acodec", "pcm_s16le",
                   "-ar", "16000", "-ac", "1", out_path]
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            if result.returncode == 0 and os.path.exists(out_path):
                with open(out_path, "rb") as f:
                    raw_data = f.read()
                os.unlink(out_path)
            os.unlink(tmp_path)
        except Exception as e:
            print(f"[STT] FFmpeg error: {e}")
            return {"transcript": ""}
    else:
        raw_data = content

    if not raw_data:
        return {"transcript": ""}

    # Step 1: STT + Voice Emotion (from this audio)
    voice_result = _call_voice_service(raw_data)
    transcript = voice_result.get("transcript", "").strip()
    voice_emotion = voice_result.get("emotion", "Neutral")

    # Step 2: Snapshot face emotion at THIS moment
    with state_lock:
        face_emotion = system_state["video_emotion"]
        history_snapshot = list(system_state.get("conversation_history", []))

    # Step 3: Update state with speech results immediately
    with state_lock:
        if transcript:
            system_state["stt_text"] = transcript
        system_state["voice_emotion"] = voice_emotion

    # Step 4: Run fusion with coordinated data
    tts_distress_threshold = int(os.getenv("TTS_DISTRESS_THRESHOLD", "0"))
    if transcript:
        print(f"[Pipeline] STT: {len(transcript)} chars: {transcript[:80]} | Face: {face_emotion} | Voice: {voice_emotion}")
        result = _call_fusion_service(
            face_emotion, voice_emotion, "N/A", transcript,
            history=history_snapshot[-4:] if history_snapshot else None,
        )
        distress = result.get("distress", 0)
        response = result.get("response", "I'm here with you.")

        # Update history
        with state_lock:
            system_state["llm_response"] = response
            system_state["distress"] = distress
            hist = system_state.get("conversation_history", [])
            hist.append({"user": transcript, "assistant": response})
            system_state["conversation_history"] = hist[-10:]

        # Step 5: TTS for the response
        if response and distress >= tts_distress_threshold:
            do_tts = False
            with state_lock:
                if not system_state["tts_generating"]:
                    system_state["tts_generating"] = True
                    system_state["tts_audio_url"] = None
                    system_state["tts_audio_b64"] = None
                    do_tts = True
            if do_tts:
                print(f"[Pipeline] TTS: {response[:80]}...")
                audio_b64, mime = _call_tts_service(response)
                if audio_b64:
                    with state_lock:
                        system_state["tts_audio_b64"] = audio_b64
                        system_state["tts_audio_mime"] = mime
                        system_state["tts_audio_url"] = f"/api/tts/latest?t={int(time.time())}"
                with state_lock:
                    system_state["tts_generating"] = False

        if current_logger:
            current_logger.log_event(system_state)

    return {"transcript": transcript, "emotion": voice_emotion, "face_emotion": face_emotion}


@app.post("/api/stt/clear")
def clear_stt():
    with state_lock:
        system_state["stt_text"] = ""
    return {"status": "cleared"}


@app.post("/api/chat/clear")
def clear_chat():
    with state_lock:
        system_state["conversation_history"] = []
        system_state["llm_response"] = "Chat cleared. How can I help?"
    return {"status": "cleared"}


@app.post("/api/browser-audio")
async def ingest_browser_audio(audio: UploadFile = File(...)):
    global VOICE_BUFFER
    with AUDIO_RECORDING_LOCK:
        if not AUDIO_RECORDING_ACTIVE:
            return {"status": "not_recording"}

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
        if 'biometric_data' in df.columns:
            df = df.drop(columns=['biometric_data'])
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
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
