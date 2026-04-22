import pyaudio
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

        # Ring buffer for audio (10 seconds)
        self.buffer_lock = threading.Lock()
        self.audio_buffer = np.zeros(self.rate * 10, dtype=np.float32)
        self.buffer_pos = 0

        # STT speech segment buffer
        self.speech_buffer = []
        self.is_speaking = False
        self.silence_chunks = 0
        self.speech_chunks = 0
        self.energy_history = deque(maxlen=50)
        self.energy_threshold = 300.0

        self.latest_transcript = ""
        self.latest_emotion = "Idle"
        self.transcript_lock = threading.Lock()

        # Models
        self.ser = SERInference()
        self.stt = STTEngine(model_size="tiny", device="cuda")

        self._running = False
        self._capture_thread = None
        self._stt_thread = None

        try:
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
            print("[Voice] Running in MOCK mode")
            self.audio_available = False
            self._mock_frame = 0

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
                    # Force process if speech exceeds 15 seconds
                    total_speech_samples = sum(len(c) for c in self.speech_buffer)
                    if total_speech_samples > self.rate * 15:
                        self.is_speaking = False
                        self._process_speech_segment()

            except Exception as e:
                print(f"[Voice] Capture error: {e}")
                time.sleep(0.1)

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

    def analyze_audio(self):
        if not self.audio_available:
            self._mock_frame += 1
            mock_patterns = ["Neutral", "Neutral", "Happy", "Neutral", "Neutral"]
            return mock_patterns[self._mock_frame % len(mock_patterns)]

        try:
            with self.buffer_lock:
                end = self.buffer_pos
                start = (end - NUM_SAMPLES) % len(self.audio_buffer)
                if start < end:
                    segment = self.audio_buffer[start:end]
                else:
                    segment = np.concatenate([self.audio_buffer[start:], self.audio_buffer[:end]])

            if len(segment) < NUM_SAMPLES * 0.8:
                return self.latest_emotion

            emotion = self.ser.predict(segment, sr=self.rate)
            if emotion and emotion not in ["Unavailable", "Error"]:
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
