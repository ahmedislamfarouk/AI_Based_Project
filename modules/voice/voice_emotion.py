import numpy as np
import time
import threading
from collections import deque

from modules.voice.ser_model import SERInference, NUM_SAMPLES
from modules.voice.stt_engine import STTEngine

class VoiceEmotionAnalyzer:
    def __init__(self, rate=16000, chunk=1024):
        self.rate = rate
        self.chunk = chunk
        self.p = None
        self.stream = None
        self.audio_available = False

        self.buffer_lock = threading.Lock()
        self.audio_buffer = np.zeros(self.rate * 10, dtype=np.float32)
        self.buffer_pos = 0

        self.browser_audio_lock = threading.Lock()
        self.browser_audio_buffer = np.zeros(self.rate * 10, dtype=np.float32)
        self.browser_audio_pos = 0
        self.browser_audio_written = 0

        self.speech_buffer = []
        self.is_speaking = False
        self.silence_chunks = 0
        self.speech_chunks = 0
        self.energy_history = deque(maxlen=50)
        self.energy_threshold = 300.0

        self.latest_transcript = ""
        self.latest_emotion = "Idle"
        self.transcript_lock = threading.Lock()

        self.ser = SERInference()
        import torch
        stt_device = "cuda" if torch.cuda.is_available() else "cpu"
        self.stt = STTEngine(model_size="tiny", device=stt_device)

        self._running = False
        self._capture_thread = None
        self._stt_thread = None

        try:
            import pyaudio
            self.p = pyaudio.PyAudio()
            self.stream = self.p.open(format=pyaudio.paInt16,
                                      channels=1,
                                      rate=self.rate,
                                      input=True,
                                      frames_per_buffer=self.chunk)
            self.audio_available = True
            print("[Voice] Audio device initialized successfully")
            self._running = True
            self._capture_thread = threading.Thread(target=self._audio_capture_loop, daemon=True)
            self._capture_thread.start()
            self._stt_thread = threading.Thread(target=self._stt_loop, daemon=True)
            self._stt_thread.start()
        except Exception as e:
            print(f"[Voice] Audio device not available: {e}")
            print("[Voice] Running in browser-audio mode. Send audio via /api/browser-audio.")
            self.audio_available = False
            self._running = True
            self._stt_thread = threading.Thread(target=self._stt_loop, daemon=True)
            self._stt_thread.start()

    def _audio_capture_loop(self):
        while self._running:
            try:
                data = self.stream.read(self.chunk, exception_on_overflow=False)
                audio_chunk = np.frombuffer(data, dtype=np.int16).astype(np.float32)

                rms = np.sqrt(np.mean(audio_chunk ** 2))
                self.energy_history.append(rms)
                if len(self.energy_history) >= 20:
                    mean_e = np.mean(self.energy_history)
                    std_e = np.std(self.energy_history) if np.std(self.energy_history) > 0 else 50
                    self.energy_threshold = np.clip(mean_e + 2.5 * std_e, 200.0, 2000.0)

                with self.buffer_lock:
                    n = len(audio_chunk)
                    if self.buffer_pos + n > len(self.audio_buffer):
                        overflow = (self.buffer_pos + n) - len(self.audio_buffer)
                        self.audio_buffer[self.buffer_pos:] = audio_chunk[:n - overflow]
                        self.audio_buffer[:overflow] = audio_chunk[n - overflow:]
                        self.buffer_pos = overflow
                    else:
                        self.audio_buffer[self.buffer_pos:self.buffer_pos + n] = audio_chunk
                        self.buffer_pos += n

                if rms > self.energy_threshold:
                    self.speech_chunks += 1
                    self.silence_chunks = 0
                    if not self.is_speaking and self.speech_chunks > 5:
                        self.is_speaking = True
                        self.speech_buffer = []
                else:
                    self.silence_chunks += 1
                    if self.is_speaking and self.silence_chunks > 20:
                        self.is_speaking = False
                        self._process_speech_segment()
                    self.speech_chunks = max(0, self.speech_chunks - 1)

                if self.is_speaking:
                    self.speech_buffer.append(audio_chunk.copy())
                    total_speech_samples = sum(len(c) for c in self.speech_buffer)
                    if total_speech_samples > self.rate * 15:
                        self.is_speaking = False
                        self._process_speech_segment()

            except Exception as e:
                print(f"[Voice] Capture error: {e}")
                time.sleep(0.1)

    def feed_browser_audio(self, audio_np):
        if audio_np is None or len(audio_np) == 0:
            return
        with self.browser_audio_lock:
            n = len(audio_np)
            if self.browser_audio_pos + n > len(self.browser_audio_buffer):
                overflow = (self.browser_audio_pos + n) - len(self.browser_audio_buffer)
                self.browser_audio_buffer[self.browser_audio_pos:] = audio_np[:n - overflow]
                self.browser_audio_buffer[:overflow] = audio_np[n - overflow:]
                self.browser_audio_pos = overflow
            else:
                self.browser_audio_buffer[self.browser_audio_pos:self.browser_audio_pos + n] = audio_np
                self.browser_audio_pos += n
            self.browser_audio_written += n

    def _process_speech_segment(self):
        if not self.speech_buffer:
            return
        segment = np.concatenate(self.speech_buffer)
        self.speech_buffer = []
        if len(segment) < self.rate * 0.5:
            return
        text = self.stt.transcribe(segment, sr=self.rate)
        if text:
            with self.transcript_lock:
                self.latest_transcript = text
            print(f"[STT] {text}")

    def _stt_loop(self):
        while self._running:
            time.sleep(2.0)

    def _get_audio_segment(self):
        src = "mic"
        segment = None
        if self.audio_available:
            with self.buffer_lock:
                end = self.buffer_pos
                start = (end - NUM_SAMPLES) % len(self.audio_buffer)
                if start < end:
                    segment = self.audio_buffer[start:end].copy()
                else:
                    segment = np.concatenate([self.audio_buffer[start:], self.audio_buffer[:end]]).copy()
            src = "mic"
        with self.browser_audio_lock:
            if self.browser_audio_written > NUM_SAMPLES * 0.5:
                end = self.browser_audio_pos
                start = (end - NUM_SAMPLES) % len(self.browser_audio_buffer)
                if start < end:
                    browser_seg = self.browser_audio_buffer[start:end].copy()
                else:
                    browser_seg = np.concatenate([self.browser_audio_buffer[start:], self.browser_audio_buffer[:end]]).copy()
                if segment is None or self.browser_audio_written > self.rate * 2:
                    segment = browser_seg
                    src = "browser"
        return segment, src

    def analyze_audio(self):
        if self.ser.model is None and self.ser.feature_extractor is None:
            return self.latest_emotion if self.latest_emotion != "Idle" else "Neutral"

        segment, src = self._get_audio_segment()
        if segment is None or len(segment) < NUM_SAMPLES * 0.3:
            return self.latest_emotion

        try:
            result = self.ser.predict(segment, sr=self.rate)
            emotion = result[0] if isinstance(result, tuple) else result
            confidence = result[1] if isinstance(result, tuple) and len(result) > 1 else 1.0
            if emotion and emotion not in ["Unavailable", "Error"] and confidence >= 0.25:
                self.latest_emotion = emotion
            return self.latest_emotion
        except Exception as e:
            print(f"[Voice] SER error: {e}")
            return self.latest_emotion

    def get_latest_transcript(self):
        with self.transcript_lock:
            return self.latest_transcript

    def clear_transcript(self):
        with self.transcript_lock:
            self.latest_transcript = ""

    def close(self):
        self._running = False
        if self._capture_thread:
            self._capture_thread.join(timeout=1)
        if self._stt_thread:
            self._stt_thread.join(timeout=1)
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass
        if self.p:
            try:
                self.p.terminate()
            except:
                pass