import io
import os
import time
import threading
import tempfile
import base64
import numpy as np
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from modules.voice.ser_model import SERInference, NUM_SAMPLES
from modules.voice.stt_engine import STTEngine

app = FastAPI(title="Voice Analysis Service", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

SAMPLE_RATE = 16000
ser = None
stt = None
_lock = threading.Lock()


@app.on_event("startup")
def startup():
    global ser, stt
    import torch
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[VoiceService] Device: {device}")
    ser = SERInference(model_path="models/ser/wavlm_hubert_optimized_seed42.pth")
    stt = STTEngine(model_size="tiny", device=device)
    print("[VoiceService] Ready.")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "ser_loaded": ser is not None and ser.model is not None,
        "stt_loaded": stt is not None and stt.model is not None,
    }


@app.post("/analyze")
async def analyze_voice(audio: UploadFile = File(...)):
    """Analyze raw audio: returns emotion and transcript."""
    if ser is None and stt is None:
        return JSONResponse(content={"error": "service_not_ready"}, status_code=503)

    content = await audio.read()
    if not content:
        return JSONResponse(content={"error": "empty_audio"}, status_code=400)

    try:
        audio_np = np.frombuffer(content, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception:
        return JSONResponse(content={"error": "invalid_audio_format"}, status_code=400)

    if len(audio_np) < SAMPLE_RATE * 0.5:
        return JSONResponse(content={"error": "audio_too_short"}, status_code=400)

    result = {"emotion": "Neutral", "confidence": 0.0, "transcript": ""}

    with _lock:
        if ser and ser.model:
            try:
                emotion, confidence = ser.predict(audio_np, sr=SAMPLE_RATE)
                result["emotion"] = emotion if emotion not in ("Unavailable", "Error") else "Neutral"
                result["confidence"] = round(confidence, 4)
            except Exception as e:
                print(f"[VoiceService] SER error: {e}")

        if stt and stt.model:
            try:
                transcript = stt.transcribe(audio_np, sr=SAMPLE_RATE)
                result["transcript"] = transcript
            except Exception as e:
                print(f"[VoiceService] STT error: {e}")

    return result


@app.post("/stt")
async def transcribe(audio: UploadFile = File(...)):
    """Speech-to-text only."""
    if stt is None or stt.model is None:
        return JSONResponse(content={"error": "stt_not_ready"}, status_code=503)

    content = await audio.read()
    if not content:
        return JSONResponse(content={"error": "empty_audio"}, status_code=400)

    try:
        audio_np = np.frombuffer(content, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception:
        return JSONResponse(content={"error": "invalid_audio_format"}, status_code=400)

    try:
        transcript = stt.transcribe(audio_np, sr=SAMPLE_RATE)
        return {"transcript": transcript}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@app.post("/ser")
async def speech_emotion(audio: UploadFile = File(...)):
    """Speech emotion recognition only."""
    if ser is None or ser.model is None:
        return JSONResponse(content={"error": "ser_not_ready"}, status_code=503)

    content = await audio.read()
    if not content:
        return JSONResponse(content={"error": "empty_audio"}, status_code=400)

    try:
        audio_np = np.frombuffer(content, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception:
        return JSONResponse(content={"error": "invalid_audio_format"}, status_code=400)

    try:
        emotion, confidence = ser.predict(audio_np, sr=SAMPLE_RATE)
        return {"emotion": emotion, "confidence": round(confidence, 4)}
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
