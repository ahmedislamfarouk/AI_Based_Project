import os
import sys
import json
import time
import asyncio
import threading
from datetime import datetime

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# --- Paths for custom modules ---
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Emotion Detection"))

# --- Imports ---
from modules.video.video_emotion import VideoEmotionAnalyzer
from modules.voice.voice_emotion import VoiceEmotionAnalyzer
from modules.biometrics.heart_rate_processor import BiometricProcessor
from core.model.inference import FusionAgent
from modules.output.tts_engine import TTSEngine
from modules.output.session_logger import SessionLogger

# --- Advanced emotion model (optional) ---
try:
    from EmotionDetection import analyze_faces_and_draw, get_face_mesh
    _face_mesh = get_face_mesh()
    REAL_MODEL_AVAILABLE = True
except Exception as e:
    print(f"[Startup] Advanced emotion model unavailable: {e}")
    REAL_MODEL_AVAILABLE = False
    _face_mesh = None

app = FastAPI(title="Multimodal Emotion Monitor", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global Shared State ---
system_state = {
    "video_emotion": "Idle",
    "voice_arousal": "Idle",
    "biometric_data": "Idle",
    "ai_recommendation": {"distress": 0, "recommendation": "Start a session to begin monitoring."}
}
running = False
current_logger = None

latest_raw_frame = None
latest_display_frame = None

state_lock = threading.Lock()
frame_lock = threading.Lock()

# --- Camera & Analyzers ---
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("[Startup] Warning: Camera index 0 not available.")
    cap = None

video_analyzer = VideoEmotionAnalyzer(cap=cap) if cap else None
voice_analyzer = VoiceEmotionAnalyzer()
biometric_processor = BiometricProcessor()
fusion_agent = FusionAgent()
tts_engine = TTSEngine()

# --- Fallback therapist text map ---
THERAPIST_RESPONSES = {
    "Happy": "You seem so happy right now! Keep embracing that positive energy.",
    "Sad": "I can see you're feeling down. That's okay — I'm here with you.",
    "Angry": "I sense some frustration. Take a deep breath with me.",
    "Fear": "You look a little worried. That's completely normal. I'm right here.",
    "Surprise": "Oh! Something caught your attention! Tell me what happened!",
    "Neutral": "I'm here with you. How are you feeling right now?",
    "Drowsiness": "You seem really tired. Maybe it's time for a short break?",
    "Yawning": "I see you yawning... Have you been getting enough rest?",
    "Head Nodding": "Your head is nodding — you might be falling asleep.",
    "Anxious/High Arousal (Close)": "I notice you're quite close. Try to relax a bit.",
    "Calm/Attentive": "You look calm and attentive. That's great.",
    "No Face Detected": "I can't see your face clearly. Please adjust your position.",
    "No Frame": "Waiting for video feed...",
    "Idle": "Start a session to begin monitoring.",
}

# --- Helpers ---

def get_state_payload():
    with state_lock:
        return {
            "running": running,
            "video_emotion": system_state["video_emotion"],
            "voice_arousal": system_state["voice_arousal"],
            "biometric_data": system_state["biometric_data"],
            "distress": system_state["ai_recommendation"].get("distress", 0),
            "recommendation": system_state["ai_recommendation"].get("recommendation", ""),
        }

# --- Background Worker Threads ---

def frame_reader():
    global latest_raw_frame
    while True:
        if cap and cap.isOpened():
            ret, frame = cap.read()
            if ret:
                frame = cv2.flip(frame, 1)
                with frame_lock:
                    latest_raw_frame = frame
        time.sleep(0.033)

def video_worker():
    global latest_display_frame, system_state
    while True:
        if not running:
            time.sleep(0.5)
            continue
        with frame_lock:
            frame = latest_raw_frame.copy() if latest_raw_frame is not None else None
        if frame is not None:
            if REAL_MODEL_AVAILABLE and _face_mesh:
                try:
                    annotated, states = analyze_faces_and_draw(frame, _face_mesh)
                    current_state = states[0] if states else "Neutral"
                except Exception as e:
                    print(f"[VideoWorker] Advanced model error: {e}")
                    annotated = frame
                    current_state = video_analyzer.analyze_frame_given(frame) if video_analyzer else "No Camera"
            else:
                current_state = video_analyzer.analyze_frame_given(frame) if video_analyzer else "No Camera"
                annotated = frame.copy()
                cv2.putText(annotated, current_state, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
            with frame_lock:
                latest_display_frame = annotated
            with state_lock:
                system_state["video_emotion"] = current_state
        else:
            with state_lock:
                system_state["video_emotion"] = "No Frame"
        time.sleep(0.5)

def voice_worker():
    global system_state
    while True:
        if not running:
            time.sleep(0.5)
            continue
        try:
            arousal = voice_analyzer.analyze_audio()
            with state_lock:
                system_state["voice_arousal"] = arousal
        except Exception as e:
            with state_lock:
                system_state["voice_arousal"] = f"Error: {e}"
        time.sleep(0.5)

def biometric_worker():
    global system_state
    while True:
        if not running:
            time.sleep(0.5)
            continue
        try:
            data = biometric_processor.analyze_biometrics()
            with state_lock:
                system_state["biometric_data"] = data
        except Exception as e:
            with state_lock:
                system_state["biometric_data"] = f"Error: {e}"
        time.sleep(1.0)

def ai_fusion_worker():
    global system_state, current_logger
    last_recommendation = ""
    while True:
        if not running:
            time.sleep(1)
            continue
        try:
            with state_lock:
                voice = system_state["voice_arousal"]
                biometric = system_state["biometric_data"]
                video = system_state["video_emotion"]

            recommendation = fusion_agent.fuse_inputs(voice, biometric, video)
            if isinstance(recommendation, str):
                try:
                    start = recommendation.find("{")
                    end = recommendation.find("}") + 1
                    recommendation = json.loads(recommendation[start:end])
                except Exception:
                    pass

            if not isinstance(recommendation, dict):
                recommendation = {"distress": 50, "recommendation": str(recommendation)}

            rec_text = recommendation.get("recommendation", "")
            distress = recommendation.get("distress", 0)

            if not rec_text or rec_text.strip().lower() in ["no action needed", "no change (mock mode)"]:
                rec_text = THERAPIST_RESPONSES.get(video, "I'm here with you.")

            if distress > 70:
                rec_text = f"I can see you're going through something. {rec_text} Take a deep breath with me."
            elif distress > 40:
                rec_text = f"{rec_text} Try to relax your shoulders."

            recommendation["recommendation"] = rec_text

            with state_lock:
                system_state["ai_recommendation"] = recommendation

            if current_logger:
                current_logger.log_event(system_state)

            if rec_text and rec_text != last_recommendation and distress >= 50:
                tts_engine.speak(rec_text)
                last_recommendation = rec_text

        except Exception as e:
            print(f"[AI Fusion] Error: {e}")
        time.sleep(5)

# Launch background threads
for target in [frame_reader, video_worker, voice_worker, biometric_worker, ai_fusion_worker]:
    threading.Thread(target=target, daemon=True).start()

# --- API Endpoints ---

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
        system_state["voice_arousal"] = "Starting..."
        system_state["biometric_data"] = "Starting..."
        system_state["ai_recommendation"] = {"distress": 0, "recommendation": "Initializing..."}
    return {"status": "started"}

@app.post("/api/stop")
def stop_session():
    global running
    running = False
    with state_lock:
        system_state["video_emotion"] = "Idle"
        system_state["voice_arousal"] = "Idle"
        system_state["biometric_data"] = "Idle"
        system_state["ai_recommendation"] = {"distress": 0, "recommendation": "Session stopped. Start again when ready."}
    return {"status": "stopped"}

@app.get("/api/history")
def get_history():
    import glob
    list_of_files = glob.glob('data/sessions/*.csv')
    if not list_of_files:
        return []
    latest = max(list_of_files, key=os.path.getctime)
    try:
        import pandas as pd
        df = pd.read_csv(latest)
        df = df.tail(100)
        return df.to_dict(orient='records')
    except Exception as e:
        return {"error": str(e)}

def generate_mjpeg():
    while True:
        with frame_lock:
            frame = latest_display_frame if latest_display_frame is not None else latest_raw_frame
        if frame is not None:
            ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
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
            await websocket.send_json(payload)
            await asyncio.sleep(1)
    except Exception:
        pass

@app.on_event("shutdown")
def shutdown_event():
    if cap and cap.isOpened():
        cap.release()
    voice_analyzer.close()
    biometric_processor.close()
    cv2.destroyAllWindows()

# --- Static files ---
app.mount("/static", StaticFiles(directory="static"), name="static")
