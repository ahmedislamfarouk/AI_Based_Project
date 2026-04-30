#!/usr/bin/env python3
"""Pre-download all heavy models into the base image."""

import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

print("[preload] Checking DeepFace emotion model...")
try:
    from deepface import DeepFace
    DeepFace.build_model('Emotion')
    print("[preload] DeepFace ready.")
except Exception as e:
    print(f"[preload] DeepFace note: {e}")

print("[preload] Checking embedding model...")
try:
    from sentence_transformers import SentenceTransformer
    SentenceTransformer('all-MiniLM-L6-v2')
    print("[preload] Embedding model ready.")
except Exception as e:
    print(f"[preload] Embedding note: {e}")

print("[preload] Checking WavLM + HuBERT...")
try:
    import torch
    from transformers import Wav2Vec2FeatureExtractor, WavLMModel, HubertModel
    Wav2Vec2FeatureExtractor.from_pretrained('microsoft/wavlm-base-plus')
    m = WavLMModel.from_pretrained('microsoft/wavlm-base-plus')
    h = HubertModel.from_pretrained('facebook/hubert-base-ls960')
    if torch.cuda.is_available():
        m = m.cuda()
        h = h.cuda()
    del m, h
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    print("[preload] WavLM + HuBERT ready.")
except Exception as e:
    print(f"[preload] WavLM/HuBERT note: {e}")

print("[preload] Checking Whisper tiny model...")
try:
    import torch
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    compute_type = 'float16' if device == 'cuda' else 'int8'
    from faster_whisper import WhisperModel
    WhisperModel('tiny', device=device, compute_type=compute_type)
    print("[preload] Whisper tiny ready.")
except Exception as e:
    print(f"[preload] Whisper note: {e}")

print("[preload] Done.")
