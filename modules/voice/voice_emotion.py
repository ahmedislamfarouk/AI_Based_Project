import pyaudio
import numpy as np
import time
from collections import deque

class VoiceEmotionAnalyzer:
    def __init__(self, rate=16000, chunk=1024):
        self.rate = rate
        self.chunk = chunk
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paInt16,
                                  channels=1,
                                  rate=self.rate,
                                  input=True,
                                  frames_per_buffer=self.chunk)
        self.rms_history = deque(maxlen=20) # ~2 seconds of audio history
        self.last_arousal = "Low"

    def analyze_audio(self):
        try:
            data = self.stream.read(self.chunk, exception_on_overflow=False)
            audio_array = np.frombuffer(data, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_array.astype(float)**2))
            self.rms_history.append(rms)
            
            avg_rms = sum(self.rms_history) / len(self.rms_history)
            
            # Use relative RMS comparison (detect spikes vs background)
            if rms > (avg_rms * 2.5) and rms > 500:
                self.last_arousal = "High (Sudden Noise/Distress)"
            elif rms > 300:
                self.last_arousal = "Moderate (Speaking)"
            else:
                self.last_arousal = "Low/Stable"
                
            return self.last_arousal
        except Exception as e:
            return f"Audio Error: {e}"

    def close(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()

if __name__ == "__main__":
    v_analyzer = VoiceEmotionAnalyzer()
    try:
        while True:
            arousal = v_analyzer.analyze_audio()
            print(f"Voice Arousal: {arousal}")
            time.sleep(0.1)
    except KeyboardInterrupt:
        v_analyzer.close()
