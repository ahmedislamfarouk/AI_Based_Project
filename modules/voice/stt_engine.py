import os
import numpy as np
import torch

class STTEngine:
    def __init__(self, model_size="tiny", device="cuda"):
        self.model = None
        self.model_size = model_size
        self.device = device
        self._load_model()

    def _load_model(self):
        try:
            from faster_whisper import WhisperModel
            compute_type = "float16" if self.device == "cuda" and torch.cuda.is_available() else "int8"
            if self.device == "cuda" and not torch.cuda.is_available():
                self.device = "cpu"
                compute_type = "int8"
            self.model = WhisperModel(self.model_size, device=self.device, compute_type=compute_type)
            print(f"[STT] Loaded Whisper {self.model_size} on {self.device} ({compute_type})")
        except Exception as e:
            print(f"[STT] Failed to load Whisper: {e}")
            self.model = None

    def transcribe(self, audio_np, sr=16000):
        if self.model is None:
            return ""
        try:
            if audio_np.dtype != np.float32:
                audio_np = audio_np.astype(np.float32)
            if audio_np.max() > 1.0 or audio_np.min() < -1.0:
                audio_np = audio_np / 32768.0

            segments, _ = self.model.transcribe(audio_np, language="en", condition_on_previous_text=False)
            text = " ".join([seg.text for seg in segments]).strip()
            return text
        except Exception as e:
            print(f"[STT] Transcription error: {e}")
            return ""
