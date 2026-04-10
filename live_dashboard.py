import streamlit as st
import cv2
import numpy as np
import time
import json

st.set_page_config(page_title="AI Emotion Monitor", layout="wide", page_icon="🧠")

st.markdown("""<style>
    .metric-card {background: #1a1a2e; padding: 20px; border-radius: 12px; border: 2px solid #16213e;}
    .rec-box {background: #0a192f; padding: 15px; border-radius: 8px; border-left: 4px solid #00ff88;}
</style>""", unsafe_allow_html=True)

st.title("🧠 AI Multimodal Emotion Monitor")
st.caption("Real-time face detection + emotion estimation + LLM recommendations")
st.markdown("---")

# Layout
col_ctrl1, col_ctrl2 = st.columns([1, 1])
with col_ctrl1:
    if st.button("▶️ Start Monitoring", type="primary", use_container_width=True):
        st.session_state.running = True
with col_ctrl2:
    if st.button("⏹️ Stop", type="secondary", use_container_width=True):
        st.session_state.running = False
        st.stop()

if 'running' not in st.session_state:
    st.session_state.running = False

col_cam, col_analysis = st.columns([2, 1])

with col_cam:
    st.subheader("📹 Live Camera + Face Tracking")
    frame_placeholder = st.empty()
    stats_placeholder = st.empty()

with col_analysis:
    st.subheader("🎭 Detected Emotions")
    emotion_placeholder = st.empty()
    st.subheader("🤖 LLM Recommendation")
    llm_placeholder = st.empty()
    st.subheader("📊 Session Data")
    log_placeholder = st.empty()

# Initialize camera
cap = cv2.VideoCapture(0)
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
mouth_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_smile.xml')

if not cap.isOpened():
    st.error("❌ Camera not found! Run with: `docker run --device=/dev/video0:/dev/video0 ...`")
    st.stop()

frame_count = 0
start_time = time.time()

# Try to import LLM (optional)
try:
    from core.model.inference import FusionAgent
    fusion = FusionAgent()
    HAS_LLM = True
except:
    HAS_LLM = False
    fusion = None

while st.session_state.running:
    ret, frame = cap.read()
    if not ret:
        break
    
    frame = cv2.flip(frame, 1)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Detect faces
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    emotions = []
    
    for (x, y, w, h) in faces:
        # Draw face rectangle
        cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
        
        # Detect eyes
        roi_gray = gray[y:y+h, x:x+w]
        roi_color = frame[y:y+h, x:x+w]
        eyes = eye_cascade.detectMultiScale(roi_gray, 1.1, 5)
        smiles = mouth_cascade.detectMultiScale(roi_gray, 1.3, 10)
        
        # Simple emotion estimation based on facial features
        has_smile = len(smiles) > 0
        has_eyes = len(eyes) >= 2
        face_area_ratio = (w * h) / (frame.shape[0] * frame.shape[1])
        
        # Emotion logic
        if has_smile and has_eyes:
            emotion = "Happy 😊"
            color = (0, 255, 0)
        elif face_area_ratio > 0.15:  # Very close to camera
            emotion = "Surprised 😲"
            color = (255, 255, 0)
        elif not has_eyes:  # Eyes not detected (closed/looking down)
            emotion = "Sad 😔"
            color = (0, 128, 255)
        else:
            emotion = "Neutral 😐"
            color = (128, 128, 128)
        
        # Label
        cv2.putText(frame, emotion, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        emotions.append(emotion)
        
        # Draw eye markers
        for (ex, ey, ew, eh) in eyes:
            cv2.rectangle(roi_color, (ex, ey), (ex+ew, ey+eh), (0, 255, 0), 1)
    
    # Stats
    elapsed = time.time() - start_time
    fps = frame_count / max(0.1, elapsed)
    cv2.putText(frame, f"AI Monitor | FPS: {fps:.1f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    
    frame_placeholder.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), 
                           channels="RGB", use_container_width=True)
    stats_placeholder.info(f"**Faces:** {len(faces)} | **Elapsed:** {elapsed:.0f}s")
    
    # Emotion display
    if emotions:
        emotion_html = ""
        for i, emo in enumerate(emotions):
            emotion_html += f"<div class='metric-card' style='font-size: 22px; margin: 10px 0;'>{emo}</div>"
        emotion_placeholder.markdown(emotion_html, unsafe_allow_html=True)
        
        # LLM call every 15 seconds
        if HAS_LLM and fusion and frame_count % 150 == 0:
            try:
                emotion_summary = ", ".join(emotions)
                rec = fusion.fuse_inputs(voice="Normal", biometric="N/A", video=emotion_summary)
                if isinstance(rec, str):
                    start_idx = rec.find("{")
                    if start_idx >= 0:
                        end_idx = rec.find("}") + 1
                        rec = json.loads(rec[start_idx:end_idx])
                if isinstance(rec, dict):
                    distress = rec.get("distress", 30)
                    recommendation = rec.get("recommendation", "Monitoring...")
                    llm_placeholder.markdown(f"""
                        <div class='rec-box'>
                            <p style='margin: 0; font-size: 16px;'><b>⚠️ Distress:</b> {distress}/100</p>
                            <p style='margin: 10px 0 0 0;'><b>💬 AI Says:</b></p>
                            <p style='margin: 5px 0 0 0; font-size: 16px;'>{recommendation}</p>
                        </div>
                    """, unsafe_allow_html=True)
            except:
                llm_placeholder.info("🤖 LLM processing...")
        
        log_placeholder.code("\n".join([f"• {e}" for e in emotions]))
    else:
        emotion_placeholder.info("👤 No faces detected - scanning...")
        llm_placeholder.info("🤖 Waiting for emotion data...")
    
    frame_count += 1
    time.sleep(0.03)

cap.release()
st.success("✅ Stopped")
