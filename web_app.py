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
    REAL_MODEL_AVAILABLE = True
    print("[Startup] Advanced emotion model (DeepFace) available.")
except Exception as e:
    print(f"[Startup] Advanced emotion model unavailable: {e}")
    REAL_MODEL_AVAILABLE = False

app = FastAPI(title="Multimodal Emotion Monitor", version="2.0")

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
    "voice_emotion": "Idle",
    "biometric_data": "Idle",
    "stt_text": "",
    "llm_response": "Start a session to begin monitoring.",
    "distress": 0,
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

# --- Helpers ---

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
    face_mesh = None
    if REAL_MODEL_AVAILABLE:
        try:
            face_mesh = get_face_mesh()
            print("[VideoWorker] DeepFace FaceMesh initialized in worker thread.")
        except Exception as e:
            print(f"[VideoWorker] Failed to init FaceMesh: {e}")
            face_mesh = None

    while True:
        if not running:
            time.sleep(0.5)
            continue
        with frame_lock:
            frame = latest_raw_frame.copy() if latest_raw_frame is not None else None
        if frame is not None:
            if REAL_MODEL_AVAILABLE and face_mesh is not None:
                try:
                    annotated, states = analyze_faces_and_draw(frame, face_mesh)
                    current_state = states[0] if states else "No Face Detected"
                except Exception as e:
                    print(f"[VideoWorker] Advanced model error: {e}")
                    annotated = frame.copy()
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
            emotion = voice_analyzer.analyze_audio()
            with state_lock:
                system_state["voice_emotion"] = emotion
        except Exception as e:
            print(f"[VoiceWorker] Error: {e}")
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
    last_stt = ""
    while True:
        if not running:
            time.sleep(1)
            continue
        try:
            with state_lock:
                face_emotion = system_state["video_emotion"]
                voice_emotion = system_state["voice_emotion"]
                biometric = system_state["biometric_data"]

            stt_text = voice_analyzer.get_latest_transcript()
            if stt_text and stt_text != last_stt:
                # New transcript detected, could trigger immediate response
                pass

            result = fusion_agent.fuse_inputs(face_emotion, voice_emotion, biometric, stt_text)
            if not isinstance(result, dict):
                result = {"distress": 50, "response": str(result)}

            distress = result.get("distress", 0)
            response = result.get("response", "I'm here with you.")

            with state_lock:
                system_state["llm_response"] = response
                system_state["distress"] = distress
                system_state["stt_text"] = stt_text

            if current_logger:
                current_logger.log_event(system_state)

            if response and response != last_recommendation and distress >= 40:
                tts_engine.speak(response)
                last_recommendation = response

            if stt_text and stt_text != last_stt:
                last_stt = stt_text
                # Optionally clear transcript after processing
                # voice_analyzer.clear_transcript()

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
        system_state["voice_emotion"] = "Starting..."
        system_state["biometric_data"] = "Starting..."
        system_state["llm_response"] = "Initializing..."
        system_state["distress"] = 0
    voice_analyzer.clear_transcript()
    return {"status": "started"}

@app.post("/api/stop")
def stop_session():
    global running
    running = False
    with state_lock:
        system_state["video_emotion"] = "Idle"
        system_state["voice_emotion"] = "Idle"
        system_state["biometric_data"] = "Idle"
        system_state["llm_response"] = "Session stopped. Start again when ready."
        system_state["distress"] = 0
        system_state["stt_text"] = ""
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
