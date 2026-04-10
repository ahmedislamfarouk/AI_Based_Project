import streamlit as st
import sys
import os

# Add Emotion Detection folder to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Emotion Detection"))

import cv2
import numpy as np
from PIL import Image
import time
import json

try:
    from EmotionDetection import analyze_faces_and_draw, get_face_mesh
    DEEPFACE_AVAILABLE = True
except:
    DEEPFACE_AVAILABLE = False

st.set_page_config(page_title="AI Emotion Monitor", layout="wide", page_icon="🧠")

# Custom CSS
st.markdown("""
    <style>
    .metric-card {background-color: #1e1e1e; padding: 20px; border-radius: 10px; border: 1px solid #333;}
    .metric-value {font-size: 32px; font-weight: bold; color: #00ff88;}
    .metric-label {font-size: 14px; color: #888;}
    </style>
""", unsafe_allow_html=True)

st.title("🧠 Multimodal AI Emotion Monitor")
st.markdown("---")

# Layout
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📹 Live Camera Feed")
    frame_placeholder = st.empty()
    emotion_bar = st.empty()

with col2:
    st.subheader("📊 Emotion Analysis")
    emotion_results = st.empty()
    
    st.subheader("🎯 Fatigue Detection")
    fatigue_status = st.empty()
    
    st.subheader("💻 System Info")
    sys_info = st.empty()
    
    if st.button("⏹️ Stop", type="primary"):
        st.stop()

# Initialize camera
cap = cv2.VideoCapture(0)
face_mesh = get_face_mesh() if DEEPFACE_AVAILABLE else None

if not cap.isOpened():
    st.error("❌ Camera not found! Run with: `docker run --device=/dev/video0:/dev/video0 ...`")
    st.stop()

st.success("✅ Camera connected | DeepFace: " + ("✅ Available" if DEEPFACE_AVAILABLE else "⚠️ Not installed"))

# Initialize state
emotion_counts = {'angry': 0, 'disgust': 0, 'fear': 0, 'happy': 0, 'sad': 0, 'surprise': 0, 'neutral': 0}
frame_count = 0
start_time = time.time()

while True:
    ret, frame = cap.read()
    if not ret:
        st.error("❌ Camera read failed")
        break
    
    frame = cv2.flip(frame, 1)
    
    # Run emotion detection
    if DEEPFACE_AVAILABLE:
        emotion_data, drowsy, yawning, nodding = analyze_faces_and_draw(frame, face_mesh)
    else:
        emotion_data = []
        drowsy = yawning = nodding = False
        faces = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml').detectMultiScale(
            cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), 1.3, 5)
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
            cv2.putText(frame, 'Face', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            emotion_data.append({'emotions': {'neutral': 100}})
    
    # Calculate FPS
    elapsed = time.time() - start_time
    fps = frame_count / max(0.1, elapsed)
    cv2.putText(frame, f"FPS: {fps:.1f} | Faces: {len(emotion_data)}", (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    
    # Display frame
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    frame_placeholder.image(frame_rgb, channels="RGB", use_container_width=True)
    
    # Update emotion counts
    current_emotions = {}
    for face_info in emotion_data:
        emotions = face_info.get('emotions', {})
        if emotions:
            dominant = max(emotions.items(), key=lambda x: x[1])
            current_emotions[dominant[0]] = current_emotions.get(dominant[0], 0) + 1
    
    # Emotion display
    emotion_display = ""
    for emo, count in current_emotions.items():
        emoji_map = {'angry': '😠', 'disgust': '🤢', 'fear': '😨', 'happy': '😊', 
                     'sad': '😢', 'surprise': '😲', 'neutral': '😐'}
        emotion_display += f"{emoji_map.get(emo, '😐')} {emo.title()}: {count} faces\n"
    
    if not emotion_display:
        emotion_display = "😐 No faces detected"
    
    emotion_results.info(emotion_display)
    
    # Fatigue status
    fatigue_text = ""
    if drowsy:
        fatigue_text = "⚠️ DROWSY - Eyes closed for extended period"
    elif yawning:
        fatigue_text = "😮 YAWNING - Possible fatigue"
    elif nodding:
        fatigue_text = "😴 NODDING - High fatigue risk"
    else:
        fatigue_text = "✅ Alert - No fatigue signs"
    
    fatigue_status.info(fatigue_text)
    
    # System info
    sys_info.markdown(f"""
    **System Status:**
    - 📹 Camera: ✅ Running
    - 🎭 Emotion AI: {'✅ DeepFace' if DEEPFACE_AVAILABLE else '⚠️ Basic'}
    - 👁️ Fatigue Detection: {'✅ Active' if DEEPFACE_AVAILABLE else '❌ Needs DeepFace'}
    - ⏱️  FPS: `{fps:.1f}`
    - 📊 Frames: `{frame_count}`
    """)
    
    frame_count += 1
    time.sleep(0.05)  # ~20 FPS for DeepFace processing

cap.release()
