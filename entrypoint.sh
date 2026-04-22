#!/bin/bash
set -e

echo "=========================================="
echo "  AI Therapist - Model Setup"
echo "=========================================="

# Download Gemma therapist model if not present
MODEL_PATH="/app/LLM/model/therapist-gemma-q4_K_M.gguf"
if [ ! -f "$MODEL_PATH" ]; then
    echo "[1/5] Downloading Gemma therapist model (~4GB, one-time)..."
    python -c "
from huggingface_hub import hf_hub_download
from pathlib import Path
hf_hub_download(
    repo_id='belal212/therapist-gemma-gguf_Q4_K_M',
    filename='therapist-gemma-q4_K_M.gguf',
    local_dir='/app/LLM/model'
)
print('Gemma model downloaded.')
"
else
    echo "[1/5] Gemma model already cached. Skipping."
fi

# Download embedding model if not present
echo "[2/5] Checking embedding model..."
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Pre-download DeepFace emotion model
echo "[3/5] Checking DeepFace emotion model..."
python -c "
from deepface import DeepFace
try:
    DeepFace.build_model('Emotion')
    print('DeepFace emotion model ready.')
except Exception as e:
    print(f'DeepFace model check skipped: {e}')
"

# Pre-download WavLM feature extractor for SER
echo "[4/5] Checking WavLM feature extractor..."
python -c "
from transformers import Wav2Vec2FeatureExtractor
Wav2Vec2FeatureExtractor.from_pretrained('microsoft/wavlm-base-plus')
print('WavLM feature extractor ready.')
"

# Pre-download faster-whisper tiny model
echo "[5/5] Checking Whisper tiny model..."
python -c "
from faster_whisper import WhisperModel
model = WhisperModel('tiny', device='cpu', compute_type='int8')
print('Whisper tiny model ready.')
"

echo "=========================================="
echo "  Models ready. Starting application..."
echo "=========================================="

# Execute the main command
exec "$@"
