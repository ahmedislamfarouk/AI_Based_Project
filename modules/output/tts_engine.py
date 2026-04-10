import pyttsx3
import threading
import time

class TTSEngine:
    def __init__(self, rate=150):
        try:
            self.engine = pyttsx3.init()
            self.engine.setProperty('rate', rate)
            self.is_speaking = False
        except Exception as e:
            print(f"TTS Initialization Error: {e}")
            self.engine = None

    def speak(self, text):
        """Speaks the given text in a separate thread to avoid blocking."""
        if not self.engine or self.is_speaking:
            return
            
        def run():
            try:
                self.is_speaking = True
                self.engine.say(text)
                self.engine.runAndWait()
                # Brief pause to avoid overlap
                time.sleep(1)
                self.is_speaking = False
            except Exception as e:
                print(f"TTS Error: {e}")
                self.is_speaking = False
            
        threading.Thread(target=run, daemon=True).start()

if __name__ == "__main__":
    tts = TTSEngine()
    tts.speak("Multimodal system ready.")
    time.sleep(3)
