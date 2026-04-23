#!/bin/bash

echo "=========================================="
echo "  AI Therapist - Model Setup"
echo "=========================================="

export TF_CPP_MIN_LOG_LEVEL=3
export TF_ENABLE_ONEDNN_OPTS=0

# Download Gemma therapist model if not present
MODEL_PATH="/app/LLM/model/therapist-gemma-q4_K_M.gguf"
if [ ! -f "$MODEL_PATH" ]; then
    echo "[1/6] Downloading Gemma therapist model (~4GB, one-time)..."
    python -c "
from huggingface_hub import hf_hub_download
from pathlib import Path
hf_hub_download(
    repo_id='belal212/therapist-gemma-gguf_Q4_K_M',
    filename='therapist-gemma-q4_K_M.gguf',
    local_dir='/app/LLM/model'
)
print('Gemma model downloaded.')
" || echo "[1/6] WARNING: Gemma model download failed. Will try on first use."
else
    echo "[1/6] Gemma model already cached. Skipping."
fi

# Download embedding model if not present
echo "[2/6] Checking embedding model..."
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')" || echo "[2/6] WARNING: Embedding model download failed."

# Pre-download DeepFace emotion model
echo "[3/6] Checking DeepFace emotion model..."
python -c "
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
from deepface import DeepFace
try:
    DeepFace.build_model('Emotion')
    print('DeepFace emotion model ready.')
except Exception as e:
    print(f'DeepFace build_model note: {e}')
    print('DeepFace will download model weights on first analysis.')
" || echo "[3/6] WARNING: DeepFace model check failed. Will download on first use."

# Pre-download WavLM feature extractor + model for SER
echo "[4/6] Checking WavLM + HuBERT models for SER..."
python -c "
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import torch
device = 'cuda' if torch.cuda.is_available() else 'cpu'
from transformers import Wav2Vec2FeatureExtractor, WavLMModel, HubertModel
Wav2Vec2FeatureExtractor.from_pretrained('microsoft/wavlm-base-plus')
wavlm = WavLMModel.from_pretrained('microsoft/wavlm-base-plus')
hubert = HubertModel.from_pretrained('facebook/hubert-base-ls960')
if device == 'cuda':
    wavlm = wavlm.to(device)
    hubert = hubert.to(device)
    print(f'WavLM + HuBERT models ready on GPU.')
else:
    print('WavLM + HuBERT models ready on CPU (no GPU detected).')
del wavlm, hubert
torch.cuda.empty_cache() if torch.cuda.is_available() else None
" || echo "[4/6] WARNING: WavLM/HuBERT model download failed. Will try at runtime."

# Pre-download faster-whisper tiny model
echo "[5/6] Checking Whisper tiny model..."
python -c "
import torch
device = 'cuda' if torch.cuda.is_available() else 'cpu'
compute_type = 'float16' if device == 'cuda' else 'int8'
from faster_whisper import WhisperModel
model = WhisperModel('tiny', device=device, compute_type=compute_type)
print(f'Whisper tiny model ready on {device} ({compute_type}).')
del model
torch.cuda.empty_cache() if torch.cuda.is_available() else None
" || echo "[5/6] WARNING: Whisper model download failed. Will download on first use."

# Pre-download DeepFace facial_expression model weights
echo "[6/6] Checking DeepFace facial expression weights..."
python -c "
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
weights_path = os.path.expanduser('~/.deepface/weights/facial_expression_model_weights.h5')
if not os.path.exists(weights_path):
    try:
        from deepface import DeepFace
        DeepFace.analyze([[1]], actions=['emotion'], enforce_detection=False, silent=True)
    except:
        pass
if os.path.exists(weights_path):
    print('DeepFace facial expression weights ready.')
else:
    print('DeepFace weights will download on first use.')
" || echo "[6/6] WARNING: DeepFace weights check failed. Will download on first use."

echo "=========================================="
echo "  Models ready. Starting application..."
echo "=========================================="

# Execute the main command
exec "$@"