import csv
import os
import time
from datetime import datetime

class SessionLogger:
    def __init__(self, log_dir="data/sessions"):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        self.filename = os.path.join(self.log_dir, f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
        self._init_csv()

    def _init_csv(self):
        with open(self.filename, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "video_emotion", "voice_emotion", "biometric_data", "distress_level", "llm_response", "stt_text"])

    def log_event(self, state):
        """Logs the current system state to CSV."""
        try:
            timestamp = datetime.now().isoformat()
            video = state.get("video_emotion", "N/A") or "N/A"
            voice = state.get("voice_emotion", state.get("voice_arousal", "N/A")) or "N/A"
            biometric = state.get("biometric_data", "N/A") or "N/A"
            stt = state.get("stt_text", "") or ""
            
            distress = state.get("distress", 0)
            if distress is None:
                distress = 0
            
            rec = state.get("llm_response", "N/A") or "N/A"
            
            if rec == "N/A" and "ai_recommendation" in state:
                blob = state["ai_recommendation"]
                if isinstance(blob, dict):
                    distress = blob.get("distress", 0) or 0
                    rec = blob.get("recommendation", "N/A") or "N/A"
                else:
                    rec = str(blob)

            with open(self.filename, mode='a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, video, voice, biometric, distress, rec, stt])
        except Exception as e:
            print(f"Logging Error: {e}")

if __name__ == "__main__":
    logger = SessionLogger()
    logger.log_event({
        "video_emotion": "Interested",
        "voice_emotion": "Neutral",
        "biometric_data": "HR: 72, EDA: 100",
        "distress": 10,
        "llm_response": "Maintain state",
        "stt_text": "I feel good"
    })
    print(f"Logged to {logger.filename}")
