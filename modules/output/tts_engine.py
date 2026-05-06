import os
import io
import time
import threading
import subprocess
import wave
import base64
import numpy as np
from pathlib import Path
from datetime import datetime

TTS_BACKEND = os.getenv("TTS_BACKEND", "local").strip().lower()
TTS_OUTPUT_DIR = Path(os.getenv("TTS_OUTPUT_DIR", "data/tts"))
TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Helper: wrap raw PCM into a proper WAV file ─────────────────────────────
def _save_pcm_as_wav(filepath, pcm_bytes, channels=1, rate=24000, sample_width=2):
    with wave.open(str(filepath), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm_bytes)


def _save_numpy_as_wav(filepath, audio_np, sr):
    """Save a numpy audio array as a WAV file."""
    if audio_np.dtype != np.int16:
        max_val = np.max(np.abs(audio_np))
        if max_val > 0:
            audio_np = (audio_np / max_val * 32767).astype(np.int16)
        else:
            audio_np = (audio_np * 32767).astype(np.int16)
    _save_pcm_as_wav(filepath, audio_np.tobytes(), channels=1 if audio_np.ndim == 1 else audio_np.shape[1], rate=sr, sample_width=2)


class LocalTTSEngine:
    """Local pyttsx3 TTS (fallback, no API needed)."""
    def __init__(self, rate=150):
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', rate)
            self.is_speaking = False
        except Exception as e:
            print(f"[LocalTTS] Initialization Error: {e}")
            self.engine = None

    def speak(self, text, on_done=None):
        if not self.engine or self.is_speaking:
            return

        def run():
            try:
                self.is_speaking = True
                self.engine.say(text)
                self.engine.runAndWait()
                time.sleep(1)
                if on_done:
                    on_done(None, "audio/wav", None)
            except Exception as e:
                print(f"[LocalTTS] Error: {e}")
            finally:
                self.is_speaking = False

        threading.Thread(target=run, daemon=True).start()


class GeminiTTSEngine:
    """
    Google Gemini Flash TTS Preview engine using google-genai SDK.
    Based on: https://ai.google.dev/gemini-api/docs/speech-generation
    """
    def __init__(self):
        self.api_key = os.environ.get("GOOGLE_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model_name = os.getenv("GEMINI_TTS_MODEL", "gemini-3.1-flash-tts-preview")
        self.voice_name = os.getenv("GEMINI_TTS_VOICE", "Kore")
        self.latest_audio_path = None
        self.latest_mime_type = "audio/wav"
        self.is_speaking = False
        self._lock = threading.Lock()
        self._client = None

        if not self.api_key:
            print("[GeminiTTS] WARNING: GOOGLE_API_KEY not set. Gemini TTS will fail.")
            return

        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
            print(f"[GeminiTTS] google-genai SDK initialized. Model: {self.model_name}, Voice: {self.voice_name}")
        except Exception as e:
            print(f"[GeminiTTS] ERROR: google-genai SDK failed to init: {e}")
            self._client = None

    def speak(self, text, on_done=None):
        """Async wrapper around generate_sync."""
        if self.is_speaking:
            print("[GeminiTTS] Already speaking, skipping")
            return

        def run():
            self.is_speaking = True
            try:
                filepath, mime, audio_b64 = self.generate_sync(text)
                if on_done:
                    on_done(filepath, mime, audio_b64)
            except Exception as e:
                print(f"[GeminiTTS] Thread error: {e}")
                import traceback
                traceback.print_exc()
                self._client = None
                if on_done:
                    on_done(None, "audio/wav", None)
            finally:
                self.is_speaking = False

        threading.Thread(target=run, daemon=True).start()

    def generate_sync(self, text):
        """
        SYNCHRONOUSLY generate TTS audio.
        Returns (wav_filepath, mime_type, audio_base64).
        """
        print(f"[GeminiTTS] === SYNC GENERATE START ===")
        print(f"[GeminiTTS] Text ({len(text)} chars): {text[:120]}...")

        if not text or not self.api_key:
            print("[GeminiTTS] ERROR: No text or no API key.")
            return None, "audio/wav", None

        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
                print("[GeminiTTS] Client re-created.")
            except Exception as e:
                print(f"[GeminiTTS] Client re-create failed: {e}")
                return None, "audio/wav", None

        from google.genai import types

        print(f"[GeminiTTS] Calling model={self.model_name} with voice={self.voice_name}")

        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=self.voice_name,
                            )
                        )
                    ),
                )
            )
        except Exception as e:
            print(f"[GeminiTTS] API call failed: {e}")
            self._client = None
            return None, "audio/wav", None

        # Extract raw PCM audio data
        if not response.candidates:
            print("[GeminiTTS] ERROR: No candidates in response.")
            return None, "audio/wav", None

        candidate = response.candidates[0]
        if not candidate.content or not candidate.content.parts:
            print("[GeminiTTS] ERROR: No content parts in response.")
            return None, "audio/wav", None

        part = candidate.content.parts[0]
        if not hasattr(part, "inline_data") or not part.inline_data:
            print("[GeminiTTS] ERROR: No inline_data in first part.")
            return None, "audio/wav", None

        pcm_data = part.inline_data.data
        print(f"[GeminiTTS] Received {len(pcm_data)} bytes of raw PCM audio.")

        # Save as proper WAV file (Gemini returns raw PCM: 24000Hz, 16-bit, mono)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"response_{ts}.wav"
        filepath = TTS_OUTPUT_DIR / filename
        _save_pcm_as_wav(filepath, pcm_data)
        print(f"[GeminiTTS] Saved WAV: {filepath}")

        latest_path = TTS_OUTPUT_DIR / "latest.wav"
        _save_pcm_as_wav(latest_path, pcm_data)
        print(f"[GeminiTTS] Saved latest WAV: {latest_path}")

        with self._lock:
            self.latest_audio_path = str(filepath)
            self.latest_mime_type = "audio/wav"

        # Encode to base64 for WebSocket delivery
        with open(filepath, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")

        print(f"[GeminiTTS] === SYNC GENERATE DONE ===")
        return str(latest_path), "audio/wav", audio_b64

    def _try_play_local(self, filepath):
        players = [
            ["ffplay", "-nodisp", "-autoexit", filepath],
            ["aplay", filepath],
            ["paplay", filepath],
        ]
        for cmd in players:
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=30, check=False)
                if result.returncode == 0:
                    break
            except FileNotFoundError:
                continue
            except Exception:
                continue

    def get_latest_audio_path(self):
        with self._lock:
            return self.latest_audio_path

    def get_latest_mime_type(self):
        with self._lock:
            return self.latest_mime_type


class Qwen3TTSEngine:
    """
    Local Qwen3-TTS engine using qwen-tts package (CustomVoice model).
    Falls back to GeminiTTS if local inference fails.
    """
    def __init__(self):
        self._model = None
        self._model_lock = threading.Lock()
        self.is_speaking = False
        self.latest_audio_path = None
        self.latest_mime_type = "audio/wav"
        self._gemini_fallback = None

        self.model_name = os.getenv("QWEN_TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
        self.speaker = os.getenv("QWEN_TTS_SPEAKER", "Ryan")
        self.language = os.getenv("QWEN_TTS_LANGUAGE", "English")
        self.device = os.getenv("QWEN_TTS_DEVICE", "cuda:0")

    def _ensure_model(self):
        if self._model is not None:
            return True
        with self._model_lock:
            if self._model is not None:
                return True
            try:
                import torch
                from qwen_tts import Qwen3TTSModel
                has_flash = False
                try:
                    import flash_attn
                    has_flash = True
                except ImportError:
                    pass
                attn = "flash_attention_2" if has_flash else "sdpa"
                print(f"[Qwen3TTS] Loading {self.model_name} on {self.device} "
                      f"(attn={attn}, speaker={self.speaker})...")
                self._model = Qwen3TTSModel.from_pretrained(
                    self.model_name,
                    device_map=self.device,
                    torch_dtype=torch.bfloat16,
                    attn_implementation=attn,
                )
                print(f"[Qwen3TTS] Model ready.")
                return True
            except Exception as e:
                print(f"[Qwen3TTS] Failed to load: {e}")
                print("[Qwen3TTS] Falling back to Gemini TTS...")
                self._gemini_fallback = GeminiTTSEngine()
                return False

    def generate_sync(self, text):
        """
        SYNCHRONOUSLY generate TTS audio via Qwen3-TTS.
        Returns (wav_filepath, mime_type, audio_base64).
        Falls back to Gemini on failure.
        """
        print(f"[Qwen3TTS] Generating: '{text[:80]}...' ({len(text)} chars)")

        if not self._ensure_model():
            if self._gemini_fallback:
                print("[Qwen3TTS] Using Gemini fallback...")
                return self._gemini_fallback.generate_sync(text)
            return None, "audio/wav", None

        try:
            import soundfile as sf
            wavs, sr = self._model.generate_custom_voice(
                text=text,
                language=self.language,
                speaker=self.speaker,
                max_new_tokens=256,
            )
            audio_np = wavs[0] if isinstance(wavs, list) else wavs

            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"response_{ts}.wav"
            filepath = TTS_OUTPUT_DIR / filename
            _save_numpy_as_wav(filepath, audio_np, sr)

            latest_path = TTS_OUTPUT_DIR / "latest.wav"
            _save_numpy_as_wav(latest_path, audio_np, sr)

            self.latest_audio_path = str(filepath)
            self.latest_mime_type = "audio/wav"

            with open(filepath, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode("utf-8")

            print(f"[Qwen3TTS] Done ({len(audio_np)} samples @ {sr}Hz, "
                  f"{len(audio_b64)} base64 bytes)")
            return str(latest_path), "audio/wav", audio_b64

        except Exception as e:
            print(f"[Qwen3TTS] Generation failed: {e}")
            import traceback
            traceback.print_exc()
            if self._gemini_fallback:
                print("[Qwen3TTS] Falling back to Gemini...")
                return self._gemini_fallback.generate_sync(text)
            return None, "audio/wav", None

    def speak(self, text, on_done=None):
        """Async wrapper."""
        if self.is_speaking:
            print("[Qwen3TTS] Already speaking, skipping")
            return

        def run():
            self.is_speaking = True
            try:
                fp, mime, b64 = self.generate_sync(text)
                if on_done:
                    on_done(fp, mime, b64)
            except Exception as e:
                print(f"[Qwen3TTS] Thread error: {e}")
                if on_done:
                    on_done(None, "audio/wav", None)
            finally:
                self.is_speaking = False

        threading.Thread(target=run, daemon=True).start()

    def get_latest_audio_path(self):
        return self.latest_audio_path

    def get_latest_mime_type(self):
        return self.latest_mime_type


class TTSEngine:
    def __init__(self, rate=150):
        self.backend = TTS_BACKEND
        self._engine = None
        if self.backend == "qwen":
            self._engine = Qwen3TTSEngine()
        elif self.backend == "gemini":
            self._engine = GeminiTTSEngine()
        else:
            self._engine = LocalTTSEngine(rate=rate)
            if getattr(self._engine, "engine", None) is None and TTS_BACKEND == "local":
                print("[TTSEngine] Local TTS failed to init. Set TTS_BACKEND=qwen for local AI voice, or TTS_BACKEND=gemini for cloud.")

    def speak(self, text, on_done=None):
        if self._engine:
            self._engine.speak(text, on_done=on_done)

    def generate_sync(self, text):
        """Synchronous generation — blocks caller thread."""
        if hasattr(self._engine, 'generate_sync'):
            return self._engine.generate_sync(text)
        print("[TTSEngine] generate_sync not available for this backend.")
        return None, "audio/wav", None

    @property
    def is_speaking(self):
        return self._engine.is_speaking if self._engine else False

    def get_latest_audio_path(self):
        if self._engine:
            return self._engine.get_latest_audio_path()
        return None

    def get_latest_mime_type(self):
        if self._engine:
            return self._engine.get_latest_mime_type()
        return "audio/wav"


if __name__ == "__main__":
    def done(path, mime, b64):
        print(f"Done: {path}, {mime}, b64_len={len(b64) if b64 else 0}")

    tts = TTSEngine()
    tts.speak("Hello, I am your AI therapist.", on_done=done)
    time.sleep(10)
