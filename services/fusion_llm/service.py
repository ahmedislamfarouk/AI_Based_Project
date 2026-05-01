import os
import sys
import time
import json
import base64
import threading
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.model.inference import FusionAgent
from modules.output.tts_engine import TTSEngine

app = FastAPI(title="Fusion LLM Service", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

fusion_agent = None
tts_engine = None
TTSEngineClass = TTSEngine
_inference_lock = threading.Lock()

TTS_OUTPUT_DIR = Path("data/tts")
TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _save_pcm_as_wav(filepath, pcm_bytes, channels=1, rate=24000, sample_width=2):
    import wave
    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm_bytes)


@app.on_event("startup")
def startup():
    global fusion_agent, tts_engine
    print("[FusionService] Loading AI models...")
    fusion_agent = FusionAgent()
    tts_engine = TTSEngine()
    print("[FusionService] Ready.")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "local_llm_loaded": fusion_agent._local_llm is not None if fusion_agent else False,
        "groq_available": fusion_agent.llm is not None if fusion_agent else False,
        "tts_backend": os.getenv("TTS_BACKEND", "gemini"),
    }


@app.post("/fuse")
def fuse_sensors(data: dict):
    """
    Fuse multimodal inputs and return therapist response.
    Body: {"face_emotion": "Happy", "voice_emotion": "Neutral", "biometric": "HR: 72", "stt_text": "I feel good"}
    """
    if fusion_agent is None:
        return JSONResponse(content={"error": "fusion_not_ready"}, status_code=503)

    face_emotion = data.get("face_emotion", "Neutral")
    voice_emotion = data.get("voice_emotion", "Neutral")
    biometric = data.get("biometric", "N/A")
    stt_text = data.get("stt_text", "")

    with _inference_lock:
        try:
            result = fusion_agent.fuse_inputs(face_emotion, voice_emotion, biometric, stt_text)
            if not isinstance(result, dict):
                result = {"distress": 50, "response": str(result)}
            return result
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/tts/generate")
def generate_tts(data: dict):
    """
    Generate TTS audio from text. Returns base64-encoded WAV.
    Body: {"text": "Hello, I am your AI therapist."}
    """
    if tts_engine is None:
        return JSONResponse(content={"error": "tts_not_ready"}, status_code=503)

    text = data.get("text", "")
    if not text:
        return JSONResponse(content={"error": "no_text"}, status_code=400)

    try:
        filepath, mime, audio_b64 = tts_engine.generate_sync(text)
        if filepath and audio_b64:
            return {
                "status": "success",
                "mime_type": mime,
                "audio_base64": audio_b64,
                "audio_base64_length": len(audio_b64),
            }
        else:
            return JSONResponse(content={"error": "tts_generation_failed"}, status_code=500)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.get("/tts/latest")
def get_latest_tts():
    """Serve the most recent TTS audio file."""
    import glob as glob_module
    files = sorted(TTS_OUTPUT_DIR.glob("latest.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return JSONResponse(content={"status": "not_found"}, status_code=404)
    latest = files[0]
    from fastapi.responses import FileResponse
    mime = "audio/wav"
    if latest.suffix == ".mp3":
        mime = "audio/mpeg"
    return FileResponse(str(latest), media_type=mime)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8003)
