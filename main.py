import threading
import time
import json
from modules.video.video_emotion import VideoEmotionAnalyzer
from modules.voice.voice_emotion import VoiceEmotionAnalyzer
from modules.biometrics.heart_rate_processor import BiometricProcessor
from core.model.inference import FusionAgent
from modules.output.tts_engine import TTSEngine
from modules.output.session_logger import SessionLogger

# --- System Shared State ---
system_state = {
    "video_emotion": "Starting...",
    "voice_arousal": "Starting...",
    "biometric_data": "Starting...",
    "ai_recommendation": {"distress": 0, "recommendation": "Initializing..."}
}

# --- Modality Worker Threads ---

def video_worker():
    global system_state
    analyzer = VideoEmotionAnalyzer()
    print("[Thread] Video Modality Started")
    try:
        while True:
            system_state["video_emotion"] = analyzer.analyze_frame()
            time.sleep(0.5)
    except Exception as e:
        print(f"[Thread] Video Modality Error: {e}")
    finally:
        analyzer.release()

def voice_worker():
    global system_state
    analyzer = VoiceEmotionAnalyzer()
    print("[Thread] Voice Modality Started")
    try:
        while True:
            system_state["voice_arousal"] = analyzer.analyze_audio()
            time.sleep(0.5)
    except Exception as e:
        print(f"[Thread] Voice Modality Error: {e}")
    finally:
        analyzer.close()

def biometric_worker():
    global system_state
    processor = BiometricProcessor()
    print("[Thread] Biometric Modality Started")
    try:
        while True:
            system_state["biometric_data"] = processor.analyze_biometrics()
            time.sleep(1.0)
    except Exception as e:
        print(f"[Thread] Biometric Modality Error: {e}")
    finally:
        processor.close()

def ai_fusion_worker():
    global system_state
    agent = FusionAgent()
    tts = TTSEngine()
    logger = SessionLogger()
    last_recommendation = ""
    print("[Thread] AI Fusion Engine Started")
    while True:
        try:
            # We poll the fusion every 3-5 seconds to avoid over-requesting LLM
            recommendation = agent.fuse_inputs(
                system_state["voice_arousal"],
                system_state["biometric_data"],
                system_state["video_emotion"]
            )
            # Try parsing if it's a JSON string from LLM
            if isinstance(recommendation, str):
                try:
                    # Look for JSON structure { ... } if LLM added text
                    start = recommendation.find("{")
                    end = recommendation.find("}") + 1
                    recommendation = json.loads(recommendation[start:end])
                except:
                    pass
            
            system_state["ai_recommendation"] = recommendation
            print(f"-- [LIVE RECOMMENDATION]: {recommendation} --")
            
            # --- Log the session event ---
            logger.log_event(system_state)
            
            # --- Speak Recommendation if significant ---
            if isinstance(recommendation, dict):
                rec_text = recommendation.get("recommendation", "")
                distress = recommendation.get("distress", 0)
                
                if rec_text and rec_text != last_recommendation and distress >= 50:
                    tts.speak(rec_text)
                    last_recommendation = rec_text
                    
            time.sleep(5)
        except Exception as e:
            print(f"[Thread] AI Fusion Error: {e}")
            time.sleep(5)

# --- Main Entry Point ---

def main():
    # 1. Start Sensing Threads
    threads = [
        threading.Thread(target=video_worker, daemon=True),
        threading.Thread(target=voice_worker, daemon=True),
        threading.Thread(target=biometric_worker, daemon=True),
        threading.Thread(target=ai_fusion_worker, daemon=True)
    ]
    
    for t in threads:
        t.start()
        
    print("\n--- MULTIMODAL EMOTION MONITORING SYSTEM READY ---")
    print("Real-time analysis is active. Press Ctrl+C to stop.")
    
    try:
        # Keep the main thread alive while workers run
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down system...")

if __name__ == "__main__":
    main()
