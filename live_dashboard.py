import streamlit as st
import cv2
import numpy as np
import time
import json
import pyaudio
from queue import Queue

st.set_page_config(page_title="AI Therapist", layout="wide", page_icon="🧠")

st.markdown("""<style>
    .therapist-msg {background: #1a1a2e; padding: 15px; border-radius: 12px; margin: 8px 0; border-left: 4px solid #00ff88;}
    .user-msg {background: #0a192f; padding: 15px; border-radius: 12px; margin: 8px 0; border-right: 4px solid #0088ff; text-align: right;}
    .emotion-card {background: #16213e; padding: 20px; border-radius: 15px; text-align: center; border: 2px solid #1e3a5f;}
</style>""", unsafe_allow_html=True)

st.title("🧠 AI Therapist - Real-Time Support")
st.caption("Your AI therapist monitors your emotions and voice to provide caring support")
st.markdown("---")

# Initialize session state properly
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
    start_btn = st.button("▶️ Start Therapy Session", type="primary", use_container_width=True)
with col2:
    stop_btn = st.button("⏹️ End Session", type="secondary", use_container_width=True)

# Layout
col_cam, col_therapy = st.columns([1.5, 1])

with col_cam:
    st.subheader("📹 Live Session")
    frame_placeholder = st.empty()
    info_placeholder = st.empty()

with col_therapy:
    st.subheader("💬 Therapist Chat")
    chat_container = st.container(height=350)
    
    st.subheader("🎭 Current Emotion")
    emotion_placeholder = st.empty()
    
    st.subheader("📊 Emotion Timeline")
    timeline_placeholder = st.empty()

# Voice detection
def record_voice(voice_queue, running_flag):
    p = pyaudio.PyAudio()
    try:
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, 
                       input=True, frames_per_buffer=1024)
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

# Start session logic - only runs ONCE
if start_btn and not st.session_state.session_started:
    st.session_state.running = True
    st.session_state.session_started = True
    st.session_state.chat_history = []
    st.session_state.emotion_data = []
    st.rerun()

if stop_btn:
    st.session_state.running = False
    st.session_state.session_started = False

# Main monitoring loop
if st.session_state.running:
    # Initialize components
    cap = cv2.VideoCapture(0)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
    
    # Voice queue
    voice_queue = Queue()
    voice_running = [True]
    voice_thread = None
    
    # Try to start voice thread
    try:
        import threading
        voice_thread = threading.Thread(target=record_voice, args=(voice_queue, voice_running), daemon=True)
        voice_thread.start()
    except:
        pass
    
    # Try LLM
    try:
        from core.model.inference import FusionAgent
        fusion = FusionAgent()
        HAS_LLM = True
    except:
        HAS_LLM = False
        fusion = None
    
    # Therapist responses (more varied)
    THERAPIST_RESPONSES = {
        "Happy": [
            "I can see you're feeling good! 😊 That's wonderful. What's bringing you joy today?",
            "You're smiling! It's great to see you in good spirits. Tell me more about what's going well.",
            "Your positive energy is wonderful. I'm glad you're feeling happy right now!"
        ],
        "Sad": [
            "I notice you seem down. 💙 I'm here for you. Would you like to talk about what's bothering you?",
            "You look a bit sad. It's okay to feel this way. I'm listening if you want to share.",
            "I can see something's weighing on you. You don't have to go through it alone. I'm here."
        ],
        "Anxious": [
            "You seem a bit tense. 💚 Try taking a deep breath with me. In... and out. I'm here to support you.",
            "I can sense some anxiety. That's okay. Let's work through it together. You're safe here.",
            "You appear worried. Remember, it's just a feeling and it will pass. I'm here with you."
        ],
        "Surprised": [
            "Something unexpected happened? 😮 I'm listening. Tell me more about what surprised you.",
            "That's an interesting reaction! What caught you off guard?"
        ],
        "Neutral": [
            "I'm here with you. 💙 How are you feeling right now? You can tell me anything.",
            "We're just sitting together quietly. That's okay too. I'm here whenever you're ready to talk."
        ]
    }
    
    frame_count = 0
    start_time = time.time()
    last_therapy_response = 0
    current_emotion = "Neutral"
    emotion_streak = {"Neutral": 0}
    response_index = {}  # Track which response to use next for each emotion
    
    # Add initial greeting only ONCE
    if not st.session_state.chat_history:
        st.session_state.chat_history.append({
            "role": "therapist",
            "message": "Hello! I'm your AI therapist. 👋 I can see your emotions through the camera and hear your voice. I'm here to support you. How are you feeling today?"
        })
    
    while st.session_state.running:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame = cv2.flip(frame, 1)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        
        # Check voice
        speaking = not voice_queue.empty()
        if speaking:
            _ = voice_queue.get()
        
        # Face and emotion detection
        new_emotion = "Neutral"
        face_detected = len(faces) > 0
        
        if face_detected:
            x, y, w, h = faces[0]
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 255), 3)
            
            roi_gray = gray[y:y+h, x:x+w]
            eyes = eye_cascade.detectMultiScale(roi_gray, 1.2, 5)
            
            face_size_ratio = (w * h) / (frame.shape[0] * frame.shape[1])
            has_eyes = len(eyes) >= 2
            
            # Better emotion logic
            if face_size_ratio > 0.2:
                new_emotion = "Anxious"
            elif speaking:
                new_emotion = "Happy"
            elif not has_eyes:
                new_emotion = "Sad"
            elif face_size_ratio > 0.12:
                new_emotion = "Surprised"
            else:
                new_emotion = "Neutral"
            
            # Color-coded label
            colors = {"Happy": (0, 255, 0), "Sad": (255, 100, 100), "Anxious": (255, 165, 0), 
                     "Surprised": (255, 255, 0), "Neutral": (128, 128, 128)}
            color = colors.get(new_emotion, (255, 255, 255))
            cv2.putText(frame, new_emotion, (x, y-15), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 3)
        
        # Emotion tracking with smoothing
        if new_emotion == current_emotion:
            emotion_streak[new_emotion] = emotion_streak.get(new_emotion, 0) + 1
        else:
            emotion_streak[new_emotion] = 0
            current_emotion = new_emotion
        
        # Confirm emotion after 15 frames (~0.75 sec)
        confirmed = current_emotion if emotion_streak.get(current_emotion, 0) >= 15 else "Scanning..."
        
        # Stats overlay
        elapsed = time.time() - start_time
        fps = frame_count / max(0.1, elapsed)
        voice_text = "🎤 Speaking" if speaking else "🎤 Listening"
        cv2.putText(frame, f"AI Therapist | FPS: {fps:.1f} | {voice_text}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        frame_placeholder.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), 
                               channels="RGB", use_container_width=True)
        info_placeholder.info(f"**Session Time:** {elapsed:.0f}s | **Faces:** {len(faces)}")
        
        # Emotion display
        emoji_map = {"Happy": "😊", "Sad": "😢", "Anxious": "😰", "Surprised": "😲", "Neutral": "😐"}
        emoji = emoji_map.get(confirmed, "👤")
        emotion_placeholder.markdown(f"""
            <div class='emotion-card'>
                <div style='font-size: 48px;'>{emoji}</div>
                <div style='font-size: 24px; margin-top: 10px;'>{confirmed}</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Therapist response every 20 seconds with NEW emotion
        if HAS_LLM and fusion and emotion_streak.get(current_emotion, 0) >= 30 and time.time() - last_therapy_response > 20:
            voice_input = "Speaking actively" if speaking else "Quiet"
            try:
                rec = fusion.fuse_inputs(voice=voice_input, biometric="N/A", video=confirmed)
                
                therapist_msg = ""
                if isinstance(rec, str):
                    start_idx = rec.find("{")
                    if start_idx >= 0:
                        end_idx = rec.find("}") + 1
                        rec = json.loads(rec[start_idx:end_idx])
                
                if isinstance(rec, dict):
                    distress = rec.get("distress", 30)
                    recommendation = rec.get("recommendation", "")
                    if recommendation:
                        therapist_msg = f"**Distress: {distress}/100** - {recommendation}"
                
                # Fallback to pre-written if LLM fails
                if not therapist_msg:
                    if current_emotion not in response_index:
                        response_index[current_emotion] = 0
                    responses = THERAPIST_RESPONSES.get(current_emotion, THERAPIST_RESPONSES["Neutral"])
                    therapist_msg = responses[response_index[current_emotion] % len(responses)]
                    response_index[current_emotion] += 1
                
                st.session_state.chat_history.append({
                    "role": "therapist",
                    "message": therapist_msg
                })
                last_therapy_response = time.time()
            except Exception as e:
                # Fallback response
                if current_emotion not in response_index:
                    response_index[current_emotion] = 0
                responses = THERAPIST_RESPONSES.get(current_emotion, THERAPIST_RESPONSES["Neutral"])
                st.session_state.chat_history.append({
                    "role": "therapist",
                    "message": responses[response_index[current_emotion] % len(responses)]
                })
                response_index[current_emotion] += 1
                last_therapy_response = time.time()
        
        # Display chat - ONLY last 5 messages
        chat_html = ""
        for msg in st.session_state.chat_history[-5:]:
            if msg["role"] == "therapist":
                chat_html += f"<div class='therapist-msg'><b>🧠 Therapist:</b><br>{msg['message']}</div>"
        
        with chat_container:
            st.markdown(chat_html, unsafe_allow_html=True)
        
        # Emotion timeline
        if frame_count % 15 == 0 and confirmed != "Scanning...":
            st.session_state.emotion_data.append(confirmed)
        
        if st.session_state.emotion_data:
            timeline_text = " → ".join([emoji_map.get(e, e) for e in st.session_state.emotion_data[-15:]])
            timeline_placeholder.info(f"**Last 15 readings:** {timeline_text}")
        
        frame_count += 1
        time.sleep(0.05)
    
    # Cleanup
    voice_running[0] = False
    cap.release()
    st.session_state.running = False
    st.success("✅ Session ended. Take care of yourself! 💙")

else:
    if not st.session_state.session_started:
        st.info("👆 Click **Start Therapy Session** to begin")
