import streamlit as st
import cv2
import numpy as np
import time
import json
import pyaudio
import threading
from queue import Queue
from datetime import datetime

st.set_page_config(page_title="AI Therapist", layout="wide", page_icon="🧠")

st.markdown("""<style>
    .chat-bubble {background: #1a1a2e; padding: 15px; border-radius: 12px; margin: 5px 0; border-left: 4px solid #00ff88;}
    .therapist-msg {background: #0a192f; padding: 15px; border-radius: 12px; margin: 10px 0; border: 1px solid #1e3a5f;}
    .emotion-tag {display: inline-block; background: #16213e; padding: 8px 15px; border-radius: 20px; margin: 3px; font-size: 16px;}
</style>""", unsafe_allow_html=True)

st.title("🧠 AI Therapist - Real-Time Emotion Support")
st.caption("Your AI therapist monitors your emotions and voice to provide real-time support")
st.markdown("---")

# Initialize session state
if 'running' not in st.session_state:
    st.session_state.running = False
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'emotion_data' not in st.session_state:
    st.session_state.emotion_data = []
if 'voice_queue' not in st.session_state:
    st.session_state.voice_queue = Queue()

# Controls
col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    start_btn = st.button("▶️ Start Session", type="primary", use_container_width=True)
with col2:
    stop_btn = st.button("⏹️ Stop", type="secondary", use_container_width=True)

if stop_btn:
    st.session_state.running = False

if start_btn:
    st.session_state.running = True
    st.session_state.chat_history = [{"role": "therapist", "message": "Hello! I'm here for you. I can see your emotions and hear your voice. How are you feeling today?"}]

# Layout
col_cam, col_therapy = st.columns([1.5, 1])

with col_cam:
    st.subheader("📹 Your Face + Voice")
    frame_placeholder = st.empty()
    voice_placeholder = st.empty()

with col_therapy:
    st.subheader("💬 AI Therapist Chat")
    chat_container = st.container()
    
    st.subheader("🎭 Current Emotion")
    emotion_placeholder = st.empty()
    
    st.subheader("📊 Emotion Timeline")
    timeline_placeholder = st.empty()

# Voice recording
def record_voice(voice_queue, running_flag):
    """Record audio and detect speaking"""
    p = pyaudio.PyAudio()
    chunk = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    
    try:
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=chunk)
        energy_threshold = 500
        speaking = False
        speaking_duration = 0
        
        while running_flag[0]:
            data = stream.read(chunk, exception_on_overflow=False)
            audio_array = np.frombuffer(data, dtype=np.int16)
            energy = np.sqrt(np.mean(audio_array.astype(float)**2))
            
            if energy > energy_threshold:
                if not speaking:
                    speaking = True
                    speaking_duration = 0
                speaking_duration += 0.06
            else:
                if speaking and speaking_duration > 1:
                    voice_queue.put("SPEAKING_DETECTED")
                speaking = False
                speaking_duration = 0
        
        stream.stop_stream()
        stream.close()
    except:
        pass
    p.terminate()

# Initialize camera
cap = cv2.VideoCapture(0)
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

if not cap.isOpened():
    st.error("❌ Camera not accessible")
    st.stop()

# Try LLM
try:
    from core.model.inference import FusionAgent
    fusion = FusionAgent()
    HAS_LLM = True
except:
    HAS_LLM = False
    fusion = None

# Therapist responses
THERAPIST_RESPONSES = {
    "Happy": "I can see you're feeling good! That's wonderful. What's bringing you joy today?",
    "Sad": "I notice you seem down. I'm here for you. Would you like to talk about what's bothering you?",
    "Angry": "I can sense some frustration. It's okay to feel this way. Let's work through it together.",
    "Surprised": "Something unexpected happened? I'm listening. Tell me more.",
    "Neutral": "I'm here with you. How are you feeling right now?",
    "Anxious": "You seem a bit tense. Try taking a deep breath. I'm here to support you."
}

voice_thread = None
voice_running = [False]
frame_count = 0
start_time = time.time()
last_therapy_response = 0
current_emotion = "Neutral"
emotion_streak = {"Neutral": 0}

while st.session_state.running:
    ret, frame = cap.read()
    if not ret:
        break
    
    frame = cv2.flip(frame, 1)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    
    # Voice status
    speaking = not st.session_state.voice_queue.empty()
    if speaking:
        _ = st.session_state.voice_queue.get()
    
    # Face and emotion detection
    new_emotion = "Neutral"
    face_detected = len(faces) > 0
    
    if face_detected:
        x, y, w, h = faces[0]
        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 255), 3)
        
        roi_gray = gray[y:y+h, x:x+w]
        eyes = eye_cascade.detectMultiScale(roi_gray, 1.2, 5)
        
        # Better emotion estimation using geometry
        face_center_x = x + w // 2
        face_center_y = y + h // 2
        face_size_ratio = (w * h) / (frame.shape[0] * frame.shape[1])
        
        has_eyes = len(eyes) >= 2
        eyes_open = has_eyes and any(ey > 5 for (_, ey, ew, eh) in eyes)
        
        # More sophisticated emotion logic
        if face_size_ratio > 0.2:
            new_emotion = "Anxious"
        elif not eyes_open and face_detected:
            new_emotion = "Sad"
        elif speaking:
            new_emotion = "Happy"
        elif face_size_ratio > 0.1:
            new_emotion = "Surprised"
        else:
            new_emotion = "Neutral"
        
        # Label with color
        colors = {"Happy": (0, 255, 0), "Sad": (255, 0, 0), "Angry": (0, 0, 255), 
                 "Surprised": (255, 255, 0), "Neutral": (128, 128, 128), "Anxious": (255, 165, 0)}
        color = colors.get(new_emotion, (255, 255, 255))
        cv2.putText(frame, new_emotion, (x, y-15), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 3)
        
        # Draw eye indicators
        for (ex, ey, ew, eh) in eyes:
            cv2.rectangle(frame, (x+ex, y+ey), (x+ex+ew, y+ey+eh), (0, 255, 0), 2)
    
    # Emotion tracking with temporal smoothing
    if new_emotion == current_emotion:
        emotion_streak[new_emotion] = emotion_streak.get(new_emotion, 0) + 1
    else:
        if new_emotion not in emotion_streak:
            emotion_streak[new_emotion] = 0
        current_emotion = new_emotion
    
    # Only consider emotion confirmed after 10 frames (0.5 sec)
    confirmed_emotion = current_emotion if emotion_streak.get(current_emotion, 0) >= 10 else "Scanning..."
    
    # Stats
    elapsed = time.time() - start_time
    fps = frame_count / max(0.1, elapsed)
    cv2.putText(frame, f"AI Therapist | FPS: {fps:.1f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    
    # Voice indicator
    voice_status = "🎤 Speaking" if speaking else "🎤 Listening..."
    cv2.putText(frame, voice_status, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
    
    frame_placeholder.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), channels="RGB", use_container_width=True)
    voice_placeholder.info(voice_status)
    
    # Emotion display
    emoji_map = {"Happy": "😊", "Sad": "😢", "Angry": "😠", "Surprised": "😲", "Neutral": "😐", "Anxious": "😰"}
    emoji = emoji_map.get(confirmed_emotion, "👤")
    emotion_placeholder.markdown(f"<div style='font-size: 28px; text-align: center; padding: 10px;'>{emoji} {confirmed_emotion}</div>", unsafe_allow_html=True)
    
    # Therapist interaction
    if HAS_LLM and fusion and emotion_streak.get(current_emotion, 0) >= 30 and time.time() - last_therapy_response > 15:
        voice_input = "Speaking detected" if speaking else "Silent"
        try:
            rec = fusion.fuse_inputs(voice=voice_input, biometric="N/A", video=confirmed_emotion)
            if isinstance(rec, str):
                start_idx = rec.find("{")
                if start_idx >= 0:
                    end_idx = rec.find("}") + 1
                    rec = json.loads(rec[start_idx:end_idx])
            
            if isinstance(rec, dict):
                recommendation = rec.get("recommendation", "")
                distress = rec.get("distress", 30)
                
                # Generate therapist response
                therapist_response = THERAPIST_RESPONSES.get(confirmed_emotion, "I'm here with you.")
                if recommendation:
                    therapist_response = recommendation
                
                st.session_state.chat_history.append({
                    "role": "therapist",
                    "message": f"({confirmed_emotion} detected - Distress: {distress}/100) {therapist_response}"
                })
                last_therapy_response = time.time()
        except Exception as e:
            pass
    
    # Display chat
    chat_html = ""
    for msg in st.session_state.chat_history[-8:]:
        if msg["role"] == "therapist":
            chat_html += f"<div class='therapist-msg'><b>🧠 Therapist:</b><br>{msg['message']}</div>"
    
    with chat_container:
        st.markdown(chat_html, unsafe_allow_html=True)
    
    # Emotion timeline
    timeline_data = st.session_state.emotion_data[-20:]
    if timeline_data:
        timeline_text = " → ".join([emoji_map.get(e, e) for e in timeline_data])
        timeline_placeholder.info(f"**History:** {timeline_text}")
    
    if frame_count % 10 == 0 and confirmed_emotion != "Scanning...":
        st.session_state.emotion_data.append(confirmed_emotion)
    
    frame_count += 1
    time.sleep(0.05)

cap.release()
st.session_state.running = False
st.success("✅ Session ended")
