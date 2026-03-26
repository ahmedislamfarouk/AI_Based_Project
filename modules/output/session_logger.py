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
            writer.writerow(["timestamp", "video_emotion", "voice_arousal", "biometric_data", "distress_level", "recommendation"])

    def log_event(self, state):
        """Logs the current system state to CSV."""
        try:
            timestamp = datetime.now().isoformat()
            video = state.get("video_emotion", "N/A")
            voice = state.get("voice_arousal", "N/A")
            biometric = state.get("biometric_data", "N/A")
            recommendation_blob = state.get("ai_recommendation", {})
            
            # Extract from dict or use raw
            if isinstance(recommendation_blob, dict):
                distress = recommendation_blob.get("distress", 0)
                rec = recommendation_blob.get("recommendation", "N/A")
            else:
                distress = 0
                rec = str(recommendation_blob)

            with open(self.filename, mode='a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([timestamp, video, voice, biometric, distress, rec])
        except Exception as e:
            print(f"Logging Error: {e}")

if __name__ == "__main__":
    logger = SessionLogger()
    logger.log_event({
        "video_emotion": "Interested",
        "voice_arousal": "Low",
        "biometric_data": "HR: 72, EDA: 100",
        "ai_recommendation": {"distress": 10, "recommendation": "Maintain state"}
    })
    print(f"Logged to {logger.filename}")
