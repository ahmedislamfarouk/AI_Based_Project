#!/bin/bash
set -e

echo "=========================================="
echo "  AI Therapist - Model Setup"
echo "=========================================="

# Download Gemma therapist model if not present
MODEL_PATH="/app/LLM/model/therapist-gemma-q4_K_M.gguf"
if [ ! -f "$MODEL_PATH" ]; then
    echo "[1/2] Downloading Gemma therapist model (~4GB, one-time)..."
    python -c "
from huggingface_hub import hf_hub_download
from pathlib import Path
hf_hub_download(
    repo_id='belal212/therapist-gemma-gguf_Q4_K_M',
    filename='therapist-gemma-q4_K_M.gguf',
    local_dir='/app/LLM/model'
)
print('✅ Gemma model downloaded.')
"
else
    echo "[1/2] Gemma model already cached. Skipping."
fi

# Download embedding model if not present
echo "[2/2] Checking embedding model..."
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

echo "=========================================="
echo "  Models ready. Starting application..."
echo "=========================================="

# Execute the main command
exec "$@"
