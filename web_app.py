import os
import sys
import json
import math
import time
import asyncio
import threading
import subprocess
import tempfile
import typing
import uuid
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Emotion Detection"))

from modules.video.video_emotion import VideoEmotionAnalyzer
from modules.video.cv_detector import detect_and_annotate
from modules.voice.voice_emotion import VoiceEmotionAnalyzer
from modules.biometrics.heart_rate_processor import BiometricProcessor
from core.model.inference import FusionAgent
from modules.output.tts_engine import TTSEngine, TTS_BACKEND
from modules.output.session_logger import SessionLogger
from modules.video.video_processor import VideoSessionProcessor

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


class SafeJSONResponse(JSONResponse):
    def render(self, content: typing.Any) -> bytes:
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

TTS_OUTPUT_DIR = Path(os.path.join(os.path.dirname(__file__), "data", "tts"))
TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
running = False
current_logger = None

latest_raw_frame = None
latest_display_frame = None

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

video_analyzer = VideoEmotionAnalyzer(cap=cap, open_default=False, fast_mode=True)
voice_analyzer = VoiceEmotionAnalyzer()

BIOMETRIC_SOURCE = os.getenv("BIOMETRIC_SOURCE", "auto").strip()
biometric_processor = BiometricProcessor(source=BIOMETRIC_SOURCE)

fusion_agent = FusionAgent()
tts_engine = TTSEngine()
video_processor = VideoSessionProcessor()

VIDEO_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "data", "video_sessions")
os.makedirs(VIDEO_UPLOAD_DIR, exist_ok=True)

video_session_results = {}
video_session_lock = threading.Lock()


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


def video_worker():
    global system_state
    while True:
        if not running:
            time.sleep(0.5)
            continue
        with frame_lock:
            frame = latest_raw_frame.copy() if latest_raw_frame is not None else None
        if frame is not None:
            current_state = video_analyzer.analyze_frame_given(frame) if video_analyzer else "No Camera"
            with state_lock:
                system_state["video_emotion"] = current_state
        else:
            with state_lock:
                system_state["video_emotion"] = "No Frame"
        time.sleep(0.5)


def display_worker():
    global latest_display_frame
    face_mesh = None
    if REAL_MODEL_AVAILABLE:
        try:
            face_mesh = get_face_mesh()
            print("[DisplayWorker] FaceMesh initialized for fast display overlay.")
        except Exception as e:
            print(f"[DisplayWorker] Failed to init FaceMesh: {e}")
            face_mesh = None

    while True:
        if not running:
            time.sleep(0.1)
            continue

        with frame_lock:
            frame = latest_raw_frame.copy() if latest_raw_frame is not None else None

        if frame is not None:
            annotated = frame.copy()
            emotion_text = ""
            with state_lock:
                emotion_text = system_state.get("video_emotion", "")

            if REAL_MODEL_AVAILABLE and face_mesh is not None:
                try:
                    from EmotionDetection import draw_face_mesh_fast
                    annotated = draw_face_mesh_fast(annotated, face_mesh, emotion_text)
                except Exception:
                    try:
                        annotated, _ = detect_and_annotate(annotated, emotion_text=emotion_text)
                    except Exception:
                        pass
            else:
                try:
                    annotated, _ = detect_and_annotate(annotated, emotion_text=emotion_text)
                except Exception:
                    pass

            with frame_lock:
                latest_display_frame = annotated

        time.sleep(0.033)


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


def _on_tts_done(filepath, mime_type, audio_b64):
    """Callback fired when Gemini TTS finishes generating audio."""
    with state_lock:
        if audio_b64:
            system_state["tts_audio_b64"] = audio_b64
            system_state["tts_audio_mime"] = mime_type
            system_state["tts_audio_url"] = f"/api/tts/latest?t={int(time.time())}"
            print(f"[TTS Callback] Audio ready: {mime_type}, b64_len={len(audio_b64)}")
        else:
            system_state["tts_audio_b64"] = None
        system_state["tts_generating"] = False


def ai_fusion_worker():
    global system_state, current_logger
    last_recommendation = ""
    last_stt = ""
    last_tts_time = 0
    tts_repeat_interval = 15  # retrigger same msg every 15s
    # Distress threshold: 0 = always speak, 40 = only when distressed
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

            stt_text = voice_analyzer.get_latest_transcript()

            result = fusion_agent.fuse_inputs(face_emotion, voice_emotion, biometric, stt_text)
            if not isinstance(result, dict):
                result = {"distress": 50, "response": str(result)}

            distress = result.get("distress", 0)
            response = result.get("response", "I'm here with you.")

            with state_lock:
                system_state["llm_response"] = response
                system_state["distress"] = distress
                system_state["stt_text"] = stt_text or ""

            if current_logger:
                current_logger.log_event(system_state)

            now = time.time()
            response_changed = response != last_recommendation
            repeat_due = (now - last_tts_time) > tts_repeat_interval

            if response and distress >= tts_distress_threshold and (response_changed or repeat_due):
                with state_lock:
                    system_state["tts_generating"] = True
                    system_state["tts_audio_url"] = None
                    system_state["tts_audio_b64"] = None
                print(f"[AI Fusion] Triggering TTS for distress={distress}: {response[:80]}...")
                tts_engine.speak(response, on_done=_on_tts_done)
                last_recommendation = response
                last_tts_time = now
                _cleanup_old_tts()

            if stt_text and stt_text != last_stt:
                last_stt = stt_text

        except Exception as e:
            print(f"[AI Fusion] Error: {e}")
            import traceback
            traceback.print_exc()
        time.sleep(3)


for target in [frame_reader, display_worker, video_worker, voice_worker, biometric_worker, ai_fusion_worker]:
    threading.Thread(target=target, daemon=True).start()


def process_video_in_thread(session_id, video_path):
    try:
        with video_session_lock:
            video_session_results[session_id]["status"] = "processing"

        print(f"[VideoSession {session_id}] Starting video processing: {video_path}")
        results = video_processor.process_video_session(video_path)
        print(f"[VideoSession {session_id}] FER={results.get('fer_emotion')}, SER={results.get('ser_emotion')}, STT_len={len(results.get('stt_text', ''))}")

        fer_emotion = results.get("fer_emotion", "Neutral")
        ser_emotion = results.get("ser_emotion", "Neutral")
        stt_text = results.get("stt_text", "")

        print(f"[VideoSession {session_id}] Running LLM fusion...")
        fusion_result = fusion_agent.fuse_inputs_fast(fer_emotion, ser_emotion, "N/A", stt_text)
        if not isinstance(fusion_result, dict):
            fusion_result = {"distress": 50, "response": str(fusion_result)}

        distress = fusion_result.get("distress", 0)
        response = fusion_result.get("response", "I'm here with you.")
        results["llm_distress"] = distress
        results["llm_response"] = response
        results["status"] = "completed"

        print(f"[VideoSession {session_id}] Completed! Distress={distress}, Response={response[:80]}...")

        # Trigger TTS for video session results too
        print(f"[VideoSession {session_id}] TTS check: backend={TTS_BACKEND}, has_response={bool(response)}")
        tts_audio_b64 = None
        tts_audio_url = None
        tts_audio_mime = "audio/wav"

        if response and TTS_BACKEND == "gemini":
            print(f"[VideoSession {session_id}] Triggering TTS SYNC (blocking)...")
            try:
                filepath, mime, audio_b64 = tts_engine.generate_sync(response)
                if filepath:
                    print(f"[VideoSession {session_id}] TTS SUCCESS: {filepath}")
                    _on_tts_done(filepath, mime, audio_b64)
                    tts_audio_b64 = audio_b64
                    tts_audio_url = f"/api/tts/latest?t={int(time.time())}"
                    tts_audio_mime = mime
                else:
                    print(f"[VideoSession {session_id}] TTS FAILED: generate_sync returned None")
            except Exception as e:
                print(f"[VideoSession {session_id}] TTS ERROR: {e}")
                import traceback
                traceback.print_exc()
            _cleanup_old_tts()
        elif response:
            print(f"[VideoSession {session_id}] Triggering async TTS...")
            tts_engine.speak(response, on_done=_on_tts_done)
            _cleanup_old_tts()
        else:
            print(f"[VideoSession {session_id}] Skipping TTS — no response text.")

        # Embed TTS info into video session results so the frontend gets it
        results["tts_audio_url"] = tts_audio_url
        results["tts_audio_mime"] = tts_audio_mime
        results["tts_audio_b64"] = tts_audio_b64

        with video_session_lock:
            video_session_results[session_id] = sanitize_for_json(results)

    except Exception as e:
        import traceback
        print(f"[VideoSession {session_id}] ERROR: {e}")
        traceback.print_exc()
        with video_session_lock:
            video_session_results[session_id]["status"] = f"error: {str(e)}"
            video_session_results[session_id]["error"] = str(e)


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
        system_state["tts_audio_url"] = None
        system_state["tts_audio_b64"] = None
        system_state["tts_generating"] = False
    return {"status": "stopped"}


@app.get("/api/tts/latest")
def get_latest_tts():
    """Serve the most recent AI-generated TTS audio file."""
    latest = _find_latest_tts_file()
    if latest is None or not latest.exists():
        return JSONResponse(content={"status": "not_found"}, status_code=404)
    mime = "audio/wav"
    if latest.suffix == ".mp3":
        mime = "audio/mpeg"
    elif latest.suffix == ".ogg":
        mime = "audio/ogg"
    elif latest.suffix == ".webm":
        mime = "audio/webm"
    return FileResponse(str(latest), media_type=mime)


@app.post("/api/tts/test")
def test_tts(text: str = "Hello, I am your AI therapist. How are you feeling today?"):
    """Manually trigger async TTS for testing purposes."""
    if not text:
        return {"status": "error", "message": "No text provided"}
    print(f"[TTS Test] Triggering async TTS for: {text[:100]}...")
    tts_engine.speak(text, on_done=_on_tts_done)
    return {"status": "tts_triggered", "text": text, "backend": TTS_BACKEND}


@app.post("/api/tts/debug")
def debug_tts(text: str = "Hello, I am your AI therapist. How are you feeling today?"):
    """
    Synchronous TTS debug endpoint. Blocks until audio is generated.
    This lets you see every error immediately in the response.
    """
    if not text:
        return {"status": "error", "message": "No text provided"}
    if TTS_BACKEND != "gemini":
        return {"status": "error", "message": f"TTS_BACKEND is '{TTS_BACKEND}', set to 'gemini' to test."}

    print(f"[TTS Debug] SYNC generating for: {text[:100]}...")
    try:
        filepath, mime, audio_b64 = tts_engine.generate_sync(text)
        if filepath:
            _on_tts_done(filepath, mime, audio_b64)
            return {
                "status": "success",
                "filepath": filepath,
                "mime_type": mime,
                "audio_base64_length": len(audio_b64) if audio_b64 else 0,
                "audio_url": "/api/tts/latest",
            }
        else:
            return {"status": "failed", "message": "generate_sync returned None. Check container logs."}
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[TTS Debug] EXCEPTION: {e}\n{tb}")
        return {"status": "error", "message": str(e), "traceback": tb}


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
    content = await audio.read()
    if not content:
        return {"status": "empty_audio"}

    content_type = audio.content_type or ""
    tmp_path = None

    if "webm" in content_type or "ogg" in content_type or "wav" in content_type or "mp4" in content_type:
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
                raw_audio = np.fromfile(out_path, dtype=np.int16).astype(np.float32)
                if len(raw_audio) > 0 and raw_audio.max() > 0:
                    raw_audio = raw_audio / 32768.0
                voice_analyzer.feed_browser_audio(raw_audio)
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
    else:
        try:
            raw_audio = np.frombuffer(content, dtype=np.int16).astype(np.float32)
            if len(raw_audio) > 0 and raw_audio.max() > 0:
                raw_audio = raw_audio / 32768.0
            voice_analyzer.feed_browser_audio(raw_audio)
        except Exception as e:
            print(f"[Audio] Raw decode error: {e}")

    return {"status": "ok"}


@app.post("/api/upload-video")
async def upload_video_session(video: UploadFile = File(...)):
    session_id = str(uuid.uuid4())[:8]
    content_type = video.content_type or "video/webm"

    ext = ".webm"
    if "mp4" in content_type:
        ext = ".mp4"
    elif "avi" in content_type:
        ext = ".avi"
    elif "mov" in content_type:
        ext = ".mov"

    save_path = os.path.join(VIDEO_UPLOAD_DIR, f"session_{session_id}{ext}")
    with open(save_path, "wb") as f:
        while True:
            chunk = await video.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)

    with video_session_lock:
        video_session_results[session_id] = {
            "status": "uploaded",
            "video_path": save_path,
            "session_id": session_id
        }

    thread = threading.Thread(
        target=process_video_in_thread,
        args=(session_id, save_path),
        daemon=True
    )
    thread.start()

    return {"session_id": session_id, "status": "processing"}


@app.get("/api/video-session/{session_id}")
def get_video_session_status(session_id: str):
    with video_session_lock:
        result = video_session_results.get(session_id)
    if result is None:
        return JSONResponse(content={"status": "not_found"}, status_code=404)
    return SafeJSONResponse(content=sanitize_for_json(result))


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
            await websocket.send_json(sanitize_for_json(payload))
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

app.mount("/static", StaticFiles(directory="static"), name="static")