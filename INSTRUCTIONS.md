# AI Therapist — Microservice Architecture

## Quick Start

```bash
cd /home/skyvision/AI_Based_Project

# One-time: build shared base (all PyTorch/TF/DeepFace — 20 min)
sudo docker build -t ai-therapist-base:latest -f Dockerfile.base .

# Build and start all services (seconds after base is built)
sudo docker compose up -d --build

# Open: http://localhost:8010
```

## Architecture

```
Browser ──► web-api (:8010) ──► face-analysis (:8001)   DeepFace + MediaPipe
           (orchestrator)   ──► voice-analysis (:8002)   Whisper + WavLM/HuBERT
                            ──► fusion-llm (:8003)       Gemma GGUF + FAISS + TTS
```

## Services

| Service | Port | Heavy Dependencies | Rebuild Time |
|---------|------|--------------------|-------------|
| `ai-therapist-base` | — | PyTorch, TF, DeepFace, Whisper, WavLM | 20 min (once) |
| `face-analysis` | 8001 | DeepFace, MediaPipe | 3 sec |
| `voice-analysis` | 8002 | Whisper, WavLM, HuBERT | 5 sec |
| `fusion-llm` | 8003 | Gemma GGUF (2.6GB), FAISS, Gemini TTS | 10 sec |
| `web-api` | 8010 | FastAPI, OpenCV only | 2 sec |

## Common Commands

```bash
# View logs
sudo docker compose logs -f              # all services
sudo docker compose logs -f fusion-llm   # just one

# Restart a service
sudo docker compose restart web-api
sudo docker compose restart fusion-llm

# Stop everything
sudo docker compose down

# Check container status
sudo docker ps
```

## How to Tweak Without Rebuilding Everything

### Change frontend UI (HTML/JS/CSS)
```
Just edit files in static/ and rebuild only web-api:
sudo docker compose up -d --build web-api   (2 seconds)

Static files are at:
  static/index.html   — main page layout, tabs, CSS
  static/js/app.js    — WebSocket, camera, audio, video session logic
```

### Change AI therapist behavior (prompts, response style)
```
Edit core/model/inference.py  (system prompt, temperature, max tokens)
Then rebuild only fusion-llm:
sudo docker compose up -d --build fusion-llm   (10 seconds)
```

### Change face emotion detection
```
Edit services/face_analysis/service.py
Then:
sudo docker compose up -d --build face-analysis   (3 seconds)
```

### Change voice/STT logic
```
Edit services/voice_analysis/service.py  or  modules/voice/ser_model.py
Then:
sudo docker compose up -d --build voice-analysis   (5 seconds)
```

### Change the API orchestrator (session logic, frame handling, WebSocket)
```
Edit services/web_api/service.py
Then:
sudo docker compose up -d --build web-api   (2 seconds)
```

### Add Python dependencies (requirements.txt)
```
Warning: this requires rebuilding the base image.
Edit requirements.txt, then:
sudo docker build -t ai-therapist-base:latest -f Dockerfile.base .
sudo docker compose up -d --build
```

## File Map (what to edit for what)

```
AI_Based_Project/
  static/
    index.html          — UI layout, tabs, CSS styles
    js/app.js           — frontend logic (WebSocket, camera, audio, TTS)
  
  services/
    web_api/service.py          — FastAPI orchestrator, session manage, frame handling
    face_analysis/service.py    — DeepFace + MediaPipe emotion detection API
    voice_analysis/service.py   — Whisper STT + WavLM/HuBERT SER API
    fusion_llm/service.py       — Gemma GGUF LLM + FAISS RAG + Gemini TTS API
  
  core/model/inference.py       — LLM fusion agent, prompt template, RAG retrieval
  modules/voice/ser_model.py    — WavLM + HuBERT fusion model definition
  modules/voice/stt_engine.py   — Whisper STT wrapper
  modules/output/tts_engine.py  — Gemini + pyttsx3 TTS engines
  
  Dockerfile.base               — Shared heavy base (PyTorch, TF, all pip deps)
  docker-compose.yml            — Service orchestration
```

## Troubleshooting

### Cannot stop containers
```
sudo snap restart docker   # restarts Docker daemon, kills all containers
```

### GPU not available in containers
```
nvidia-smi                  # check GPU
sudo apt install nvidia-container-toolkit  # may need installation
```

### Container keeps restarting
```
sudo docker logs ai_based_project-web-api-1 --tail=50
```

### Port already in use
```
sudo ss -tlnp | grep 8010   # check what's using the port
sudo kill -9 <PID>           # kill it
```

## Environment Variables

Set in `.env` or `docker-compose.yml` environment section:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_MODE` | `local` | `local` for Gemma, `api` for Groq |
| `GROQ_API_KEY` | — | Groq API key (fallback LLM) |
| `GOOGLE_API_KEY` | — | Google AI key (Gemini TTS) |
| `TTS_BACKEND` | `gemini` | TTS engine (`gemini` or `local`) |
| `TTS_DISTRESS_THRESHOLD` | `0` | 0=always speak, 40+=only when distressed |
| `CAMERA_SOURCE` | `browser` | `browser` or `device` |
| `CAMERA_ID` | `0` | Device camera index |
