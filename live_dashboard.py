import streamlit as st
import sys
import os
import json
import time
from datetime import datetime

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Emotion Detection"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "core/model"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "modules/output"))

import cv2
import numpy as np

# Import modules
try:
    from EmotionDetection import analyze_faces_and_draw, get_face_mesh
    EMOTION_AI = True
except:
    EMOTION_AI = False

try:
    from inference import FusionAgent
    LLM_AVAILABLE = True
except:
    LLM_AVAILABLE = False

try:
    from session_logger import SessionLogger
    LOGGER_AVAILABLE = True
except:
    LOGGER_AVAILABLE = False

st.set_page_config(page_title="AI Emotion Monitor", layout="wide", page_icon="🧠")

st.markdown("""<style>
    .metric-card {background: #1a1a2e; padding: 20px; border-radius: 12px; border: 2px solid #16213e;}
    .emotion-happy {color: #00ff88;} .emotion-sad {color: #0088ff;}
    .emotion-angry {color: #ff0044;} .emotion-fear {color: #ff8800;}
    .emotion-neutral {color: #888888;} .emotion-surprise {color: #ffff00;}
    .rec-box {background: #0a192f; padding: 15px; border-radius: 8px; border-left: 4px solid #00ff88;}
</style>""", unsafe_allow_html=True)

st.title("🧠 AI Multimodal Emotion Monitor")
st.caption("Real-time emotion detection + LLM recommendations")
st.markdown("---")

# Controls
col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([1, 1, 3])
with col_ctrl1:
    start_btn = st.button("▶️ Start", type="primary", use_container_width=True)
with col_ctrl2:
    stop_btn = st.button("⏹️ Stop", type="secondary", use_container_width=True)

# Initialize session state
if 'running' not in st.session_state:
    st.session_state.running = False
if 'emotion_log' not in st.session_state:
    st.session_state.emotion_log = []

if stop_btn:
    st.session_state.running = False
    st.stop()

if start_btn:
    st.session_state.running = True

# Layout
col_cam, col_analysis = st.columns([2, 1])

with col_cam:
    st.subheader("📹 Live Camera + Emotion Detection")
    frame_placeholder = st.empty()
    stats_placeholder = st.empty()

with col_analysis:
    st.subheader("🎭 Real-Time Emotions")
    emotion_placeholder = st.empty()
    
    st.subheader("🤖 LLM Analysis")
    llm_placeholder = st.empty()
    
    st.subheader("📊 Session Log")
    log_placeholder = st.empty()

# Initialize components
cap = cv2.VideoCapture(0)
face_mesh = get_face_mesh() if EMOTION_AI else None
fusion = FusionAgent() if LLM_AVAILABLE else None
logger = SessionLogger() if LOGGER_AVAILABLE else None

if not cap.isOpened():
    st.error("❌ Camera not found")
    st.stop()

frame_count = 0
start_time = time.time()
last_llm_call = 0
current_states = []

# Main loop
while st.session_state.running:
    ret, frame = cap.read()
    if not ret:
        break
    
    frame = cv2.flip(frame, 1)
    
    # Run emotion detection
    if EMOTION_AI:
        frame, current_states = analyze_faces_and_draw(frame, face_mesh)
    else:
        current_states = ["No Face"]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml').detectMultiScale(gray, 1.3, 5)
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
    
    # Stats
    elapsed = time.time() - start_time
    fps = frame_count / max(0.1, elapsed)
    cv2.putText(frame, f"AI Emotion Monitor | FPS: {fps:.1f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    
    frame_placeholder.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), 
                           channels="RGB", use_container_width=True)
    stats_placeholder.info(f"**Active Faces:** {len(current_states)} | **Time:** {elapsed:.0f}s")
    
    # Emotion display
    if current_states and current_states != ["No Face"]:
        emotion_html = ""
        for i, state in enumerate(current_states):
            color_class = f"emotion-{state.lower()}"
            emoji_map = {'happy': '😊', 'sad': '😢', 'angry': '😠', 'fear': '😨',
                        'neutral': '😐', 'surprise': '😲', 'Drowsiness': '😴',
                        'Yawning': '😮', 'Head Nodding': '💤'}
            emoji = emoji_map.get(state, '👤')
            emotion_html += f"<div class='metric-card'><span class='{color_class}' style='font-size: 28px;'>{emoji} {state}</span></div>"
        emotion_placeholder.markdown(emotion_html, unsafe_allow_html=True)
        
        # Call LLM every 10 seconds
        if LLM_AVAILABLE and time.time() - last_llm_call > 10:
            emotion_summary = ", ".join(current_states)
            try:
                rec = fusion.fuse_inputs(
                    voice="Normal",
                    biometric="N/A",
                    video=emotion_summary
                )
                if isinstance(rec, str):
                    start = rec.find("{")
                    if start >= 0:
                        end = rec.find("}") + 1
                        rec = json.loads(rec[start:end])
                if isinstance(rec, dict):
                    distress = rec.get("distress", 0)
                    recommendation = rec.get("recommendation", "No recommendation")
                    llm_placeholder.markdown(f"""
                        <div class='rec-box'>
                            <p style='margin: 0; font-size: 16px;'><b>⚠️ Distress Level:</b> {distress}/100</p>
                            <p style='margin: 10px 0 0 0; font-size: 18px;'><b>💬 Recommendation:</b></p>
                            <p style='margin: 5px 0 0 0;'>{recommendation}</p>
                        </div>
                    """, unsafe_allow_html=True)
                last_llm_call = time.time()
            except Exception as e:
                llm_placeholder.error(f"LLM Error: {e}")
        
        # Log session
        if logger and frame_count % 30 == 0:
            try:
                logger.log_event({
                    "video_emotion": emotion_summary,
                    "voice_arousal": "Normal",
                    "distress_level": 30,
                    "recommendation": "Monitoring"
                })
            except:
                pass
        
        # Session log display
        session_text = "\n".join([f"• {s}" for s in current_states])
        log_placeholder.code(session_text if session_text else "Waiting for data...")
    else:
        emotion_placeholder.info("👤 No faces detected - scanning...")
        llm_placeholder.info("🤖 Waiting for emotion data to analyze...")
    
    frame_count += 1
    time.sleep(0.05)

cap.release()
st.session_state.running = False
st.success("✅ Camera stopped")
