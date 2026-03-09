import pyaudio
import numpy as np
import time

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
        self.last_arousal = "Low"

    def analyze_audio(self):
        try:
            data = self.stream.read(self.chunk, exception_on_overflow=False)
            audio_array = np.frombuffer(data, dtype=np.int16)
            rms = np.sqrt(np.mean(audio_array**2))
            
            # Simple thresholding logic: energy maps to arousal
            if rms > 500:
                self.last_arousal = "High (Speaking/Anxious)"
            elif rms > 100:
                self.last_arousal = "Moderate"
            else:
                self.last_arousal = "Low/Silent"
                
            return self.last_arousal
        except Exception:
            return "Audio Error"

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
            time.sleep(0.5)
    except KeyboardInterrupt:
        v_analyzer.close()
