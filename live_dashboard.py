import streamlit as st
import sys
import os
import cv2
import numpy as np
import time
import json
import pyaudio
import threading
from queue import Queue

# Add Emotion Detection folder to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Emotion Detection"))

try:
    from EmotionDetection import analyze_faces_and_draw, get_face_mesh
    REAL_MODEL_AVAILABLE = True
except Exception as e:
    print(f"Real model failed to load: {e}")
    REAL_MODEL_AVAILABLE = False

st.set_page_config(page_title="AI Therapist", layout="wide", page_icon="🧠")

st.markdown("""<style>
    .therapist-msg {background: #1a1a2e; padding: 15px; border-radius: 12px; margin: 8px 0; border-left: 4px solid #00ff88;}
    .emotion-card {background: #16213e; padding: 20px; border-radius: 15px; text-align: center; border: 2px solid #1e3a5f;}
</style>""", unsafe_allow_html=True)

st.title("🧠 AI Therapist - Powered by DeepFace")
st.caption(f"Using: {'Real DeepFace Model' if REAL_MODEL_AVAILABLE else 'Lightweight Fallback'}")
st.markdown("---")

# Initialize session state
if 'running' not in st.session_state:
    st.session_state.running = False
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'session_started' not in st.session_state:
    st.session_state.session_started = False
if 'emotion_data' not in st.session_state:
    st.session_state.emotion_data = []

# Controls
col1, col2 = st.columns([1, 1])
with col1:
    if st.button("▶️ Start Therapy Session", type="primary", use_container_width=True):
        st.session_state.running = True
        st.session_state.session_started = True
        st.session_state.chat_history = [{"role": "therapist", "message": "Hello! I'm your AI therapist. I'm analyzing your real emotions right now. How can I help you?"}]
        st.session_state.emotion_data = []
        st.rerun()
with col2:
    if st.button("⏹️ End Session", type="secondary", use_container_width=True):
        st.session_state.running = False
        st.session_state.session_started = False
        st.stop()

# Layout
col_cam, col_therapy = st.columns([1.5, 1])

with col_cam:
    st.subheader("📹 Live Analysis")
    frame_placeholder = st.empty()
    info_placeholder = st.empty()

with col_therapy:
    st.subheader("💬 Therapist Chat")
    chat_container = st.container(height=350)
    
    st.subheader("🎭 Real-Time Emotion")
    emotion_placeholder = st.empty()
    
    st.subheader("📊 Fatigue & State")
    fatigue_placeholder = st.empty()

# Voice Detection
def record_voice(voice_queue, running_flag):
    p = pyaudio.PyAudio()
    try:
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=1024)
        speaking = False
        speaking_duration = 0
        while running_flag[0]:
            data = stream.read(1024, exception_on_overflow=False)
            audio_array = np.frombuffer(data, dtype=np.int16)
            energy = np.sqrt(np.mean(audio_array.astype(float)**2))
            if energy > 500:
                speaking = True
                speaking_duration += 0.06
            else:
                if speaking and speaking_duration > 1:
                    voice_queue.put("SPEAKING")
                speaking = False
                speaking_duration = 0
        stream.stop_stream()
        stream.close()
    except:
        pass
    p.terminate()

# Main Loop
if st.session_state.running:
    cap = cv2.VideoCapture(0)
    voice_queue = Queue()
    voice_running = [True]
    
    try:
        voice_thread = threading.Thread(target=record_voice, args=(voice_queue, voice_running), daemon=True)
        voice_thread.start()
    except:
        pass
    
    face_mesh = get_face_mesh() if REAL_MODEL_AVAILABLE else None
    
    # Try LLM
    try:
        from core.model.inference import FusionAgent
        fusion = FusionAgent()
        HAS_LLM = True
    except:
        HAS_LLM = False
        fusion = None
    
    frame_count = 0
    start_time = time.time()
    last_response_time = 0
    current_state = "Neutral"
    
    THERAPIST_RESPONSES = {
        "Happy": "I can see you're feeling good! 😊 What's bringing you joy?",
        "Sad": "I notice you seem down. 💙 I'm here for you. Want to talk about it?",
        "Angry": "I sense some frustration. 😤 It's okay. Let's breathe through it.",
        "Fear": "You look a bit scared. 😰 I'm here to keep you safe.",
        "Surprise": "Something unexpected happened? 😲 Tell me more.",
        "Neutral": "I'm here with you. 💙 How are you feeling?",
        "Drowsiness": "You seem very tired/sleepy. 😴 Please rest if you can.",
        "Yawning": "I see you yawning. 😮 Are you getting enough sleep?",
        "Head Nodding": "Your head is nodding. 😴 You might be falling asleep."
    }
    
    while st.session_state.running:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame = cv2.flip(frame, 1)
        speaking = not voice_queue.empty()
        if speaking:
            _ = voice_queue.get()
        
        # Use REAL model if available
        if REAL_MODEL_AVAILABLE and face_mesh:
            try:
                frame, states = analyze_faces_and_draw(frame, face_mesh)
                # states is a list like ["Happy", "Drowsiness", "Yawning"]
                current_state = states[0] if states else "Neutral"
            except Exception as e:
                # Fallback to simple face detection if real model fails on a frame
                current_state = "Neutral"
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml').detectMultiScale(gray, 1.3, 5)
                for (x, y, w, h) in faces:
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 255), 2)
        else:
            # Fallback
            current_state = "Neutral"
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml').detectMultiScale(gray, 1.3, 5)
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 255), 2)
                cv2.putText(frame, "Neutral", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # Overlay stats
        elapsed = time.time() - start_time
        fps = frame_count / max(0.1, elapsed)
        voice_text = "🎤 Speaking" if speaking else "🎤 Listening"
        cv2.putText(frame, f"AI Therapist (DeepFace) | FPS: {fps:.1f} | {voice_text}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        frame_placeholder.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), channels="RGB", use_container_width=True)
        info_placeholder.info(f"**Session:** {elapsed:.0f}s")
        
        # Display Emotion
        emoji_map = {"Happy": "😊", "Sad": "😢", "Angry": "😠", "Fear": "😨", "Surprise": "😲", 
                     "Neutral": "😐", "Drowsiness": "😴", "Yawning": "😮", "Head Nodding": "💤"}
        emoji = emoji_map.get(current_state, "👤")
        emotion_placeholder.markdown(f"""
            <div class='emotion-card'>
                <div style='font-size: 48px;'>{emoji}</div>
                <div style='font-size: 24px; margin-top: 10px;'>{current_state}</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Fatigue Info
        fatigue_info = "✅ Alert"
        if current_state in ["Drowsiness", "Yawning", "Head Nodding"]:
            fatigue_info = f"⚠️ {current_state} detected!"
        fatigue_placeholder.info(fatigue_info)
        
        # Therapist Logic (every 10 seconds)
        if time.time() - last_response_time > 10:
            voice_input = "Speaking" if speaking else "Silent"
            response = ""
            
            if HAS_LLM and fusion:
                try:
                    rec = fusion.fuse_inputs(voice=voice_input, biometric="N/A", video=current_state)
                    if isinstance(rec, str):
                        start_idx = rec.find("{")
                        if start_idx >= 0:
                            end_idx = rec.find("}") + 1
                            rec = json.loads(rec[start_idx:end_idx])
                    if isinstance(rec, dict):
                        response = rec.get("recommendation", "")
                except:
                    pass
            
            if not response:
                response = THERAPIST_RESPONSES.get(current_state, "I'm listening.")
            
            st.session_state.chat_history.append({
                "role": "therapist",
                "message": f"**[{current_state}]** {response}"
            })
            last_response_time = time.time()
        
        # Display Chat
        chat_html = ""
        for msg in st.session_state.chat_history[-6:]:
            chat_html += f"<div class='therapist-msg'><b>🧠 Therapist:</b><br>{msg['message']}</div>"
        with chat_container:
            st.markdown(chat_html, unsafe_allow_html=True)
        
        frame_count += 1
        time.sleep(0.05) # 20 FPS max to save CPU for DeepFace
    
    voice_running[0] = False
    cap.release()
    st.success("✅ Session ended.")
