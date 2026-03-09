import threading
import time
import json
import asyncio
import websockets
from modules.video.video_emotion import VideoEmotionAnalyzer
from modules.voice.voice_emotion import VoiceEmotionAnalyzer
from modules.biometrics.heart_rate_processor import BiometricProcessor
from core.model.inference import FusionAgent

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
            time.sleep(5)
        except Exception as e:
            print(f"[Thread] AI Fusion Error: {e}")
            time.sleep(5)

# --- WebSocket Server (To communicate with VR Engine) ---

async def handler(websocket, path):
    print(f"[WebSocket] VR Engine Connected")
    while True:
        # Push the full system state as JSON every second
        await websocket.send(json.dumps(system_state))
        await asyncio.sleep(1.0)

async def start_websocket_server(port=8765):
    print(f"[WebSocket] Server starting on port {port}")
    async with websockets.serve(handler, "localhost", port):
        await asyncio.future()  # Run forever

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
        
    # 2. Start Async WebSocket Server in Main Thread
    print("\n--- EMOTION-ADAPTIVE VR SYSTEM READY ---")
    print("Use Python for sensor analysis and Unity/Unreal for the VR room.")
    
    try:
        asyncio.run(start_websocket_server())
    except KeyboardInterrupt:
        print("\nShutting down system...")

if __name__ == "__main__":
    main()
