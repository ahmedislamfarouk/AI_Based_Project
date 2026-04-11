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
    .therapist-msg {
        background: linear-gradient(135deg, #0a2a4a 0%, #0d3b66 100%);
        padding: 50px 55px;
        border-radius: 24px;
        margin: 25px 0;
        border-left: 10px solid #00ff88;
        color: #ffffff;
        text-align: center;
        box-shadow: 0 12px 48px rgba(0, 255, 136, 0.2);
    }
    .therapist-msg .label {
        display: block;
        color: #00ff88;
        font-size: 36px;
        font-weight: bold;
        margin-bottom: 20px;
        letter-spacing: 3px;
    }
    .therapist-msg .emotion-tag {
        display: inline-block;
        background: rgba(255, 204, 0, 0.15);
        padding: 10px 30px;
        border-radius: 40px;
        font-size: 38px;
        margin-bottom: 20px;
        color: #ffcc00;
        border: 2px solid rgba(255, 204, 0, 0.3);
    }
    .therapist-msg .response-text {
        font-size: 52px;
        font-weight: bold;
        display: block;
        margin-top: 15px;
        line-height: 1.4;
    }
    .emotion-card {
        background: #16213e;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        border: 2px solid #1e3a5f;
    }
    .status-bar {
        display: flex;
        justify-content: center;
        gap: 30px;
        padding: 15px;
        background: #1a1a2e;
        border-radius: 12px;
        margin-bottom: 15px;
    }
    .status-item {
        text-align: center;
        font-size: 20px;
        color: #b0b0b0;
    }
    .status-item .value {
        font-size: 28px;
        font-weight: bold;
        color: #ffffff;
        margin-top: 5px;
    }
    .listening-indicator {
        text-align: center;
        padding: 10px;
        font-size: 18px;
        color: #888;
    }
    .chat-section-title {
        font-size: 36px;
        font-weight: bold;
        color: #00ff88;
        margin-bottom: 25px;
        text-align: center;
        letter-spacing: 2px;
    }
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
        st.session_state.chat_history = [{"role": "therapist", "message": "Welcome! 🧠 I'm your AI therapist. I'll be monitoring your emotions in real-time. How are you feeling right now? Take your time — I'm here to listen."}]
        st.session_state.emotion_data = []
        st.rerun()
with col2:
    if st.button("⏹️ End Session", type="secondary", use_container_width=True):
        st.session_state.running = False
        st.session_state.session_started = False
        st.stop()

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

    # Placeholders for vertical layout
    frame_placeholder = st.empty()
    status_placeholder = st.empty()
    emotion_placeholder = st.empty()
    therapist_placeholder = st.empty()
    listen_placeholder = st.empty()

    THERAPIST_RESPONSES = {
        "Happy": "You seem so happy right now! 😊 Keep embracing that positive energy. What's making you feel good today?",
        "Sad": "I can see you're feeling down. 💙 That's okay — I'm here with you. Want to share what's on your mind?",
        "Angry": "I sense some frustration coming through. 😤 Take a deep breath with me... in... and out. You've got this.",
        "Fear": "You look a little worried. 😰 That's completely normal. I'm right here with you. You're safe.",
        "Surprise": "Oh! Something caught your attention! 😲 Tell me what happened — I'm curious!",
        "Neutral": "I'm here with you. 💙 Take your time. How are you feeling right now?",
        "Drowsiness": "You seem really tired. 😴 Maybe it's time for a short break? Your wellbeing matters.",
        "Yawning": "I see you yawning... 😮 Have you been getting enough rest lately? Don't forget to take care of yourself.",
        "Head Nodding": "Your head is nodding — you might be falling asleep. 💤 Consider resting if you can."
    }

    # Track last displayed message to avoid re-rendering
    last_displayed_message = None

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
                current_state = states[0] if states else "Neutral"
            except Exception as e:
                current_state = "Neutral"
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml').detectMultiScale(gray, 1.3, 5)
                for (x, y, w, h) in faces:
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 255), 2)
        else:
            current_state = "Neutral"
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml').detectMultiScale(gray, 1.3, 5)
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 255), 2)
                cv2.putText(frame, "Neutral", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # Overlay stats on frame
        elapsed = time.time() - start_time
        fps = frame_count / max(0.1, elapsed)
        voice_text = "🎤 Speaking" if speaking else "🎤 Listening"
        cv2.putText(frame, f"AI Therapist | FPS: {fps:.1f} | {voice_text}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        # Show live video feed (centered)
        frame_placeholder.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), channels="RGB", use_container_width=True)

        # Status bar below video
        emoji_map = {"Happy": "😊", "Sad": "😢", "Angry": "😠", "Fear": "😨", "Surprise": "😲",
                     "Neutral": "😐", "Drowsiness": "😴", "Yawning": "😮", "Head Nodding": "💤"}
        emoji = emoji_map.get(current_state, "👤")
        mic_status = "🟢 Speaking" if speaking else "🔴 Listening"
        status_placeholder.markdown(f"""
            <div class="status-bar">
                <div class="status-item">
                    🎭 Detected Emotion
                    <div class="value">{emoji} {current_state}</div>
                </div>
                <div class="status-item">
                    🎤 Microphone
                    <div class="value">{mic_status}</div>
                </div>
                <div class="status-item">
                    ⏱️ Session Time
                    <div class="value">{elapsed:.0f}s</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Therapist Logic (every 10 seconds)
        if frame_count == 0 or time.time() - last_response_time > 10:
            voice_input = "Speaking" if speaking else "Silent"
            response = ""

            if HAS_LLM and fusion:
                try:
                    rec = fusion.fuse_inputs(voice_input, "N/A", current_state)
                    if isinstance(rec, str):
                        start_idx = rec.find("{")
                        if start_idx >= 0:
                            end_idx = rec.find("}") + 1
                            rec = json.loads(rec[start_idx:end_idx])
                    if isinstance(rec, dict):
                        raw_rec = rec.get("recommendation", "")
                        distress = rec.get("distress", 50)
                        # Clean up the response — remove robotic phrases
                        raw_rec = raw_rec.replace("No action needed", "").replace("no action needed", "").strip()
                        # Make response more conversational
                        if raw_rec:
                            if distress > 70:
                                response = f"I can see you're going through something right now. {raw_rec} Take a deep breath with me."
                            elif distress > 40:
                                response = f"{raw_rec} Try to relax your shoulders and take a slow breath."
                            else:
                                response = f"{raw_rec} I'm right here with you."
                except Exception as e:
                    print(f"LLM call failed: {e}")
                    pass

            # If LLM didn't give us a good response, use the caring fallback
            if not response:
                response = THERAPIST_RESPONSES.get(current_state, "I'm here with you. 💙 How are you feeling?")

            # Only update if the message actually changed
            new_message = f"**[{current_state}]** {response}"
            if new_message != last_displayed_message:
                last_displayed_message = new_message
                st.session_state.chat_history = [{"role": "therapist", "message": new_message}]
                last_response_time = time.time()

        # Render the therapist response using a SINGLE placeholder (replaces previous content)
        if st.session_state.chat_history:
            msg = st.session_state.chat_history[-1]
            raw = msg['message']
            if raw.startswith("**[") and "]**" in raw:
                bracket_end = raw.index("]**") + 3
                emotion_tag = raw[3:raw.index("]**")]
                response_text = raw[bracket_end:].strip()
                emoji_map = {"Happy": "😊", "Sad": "😢", "Angry": "😠", "Fear": "😨", "Surprise": "😲",
                             "Neutral": "😐", "Drowsiness": "😴", "Yawning": "😮", "Head Nodding": "💤"}
                emoji = emoji_map.get(emotion_tag, "🎭")
                chat_html = f"""
                    <div style="background: linear-gradient(135deg, #0a2a4a 0%, #0d3b66 100%); padding: 50px 55px; border-radius: 24px; margin: 25px 0; border-left: 10px solid #00ff88; color: #ffffff; text-align: center; box-shadow: 0 12px 48px rgba(0, 255, 136, 0.2);">
                        <div style="color: #00ff88; font-size: 36px; font-weight: bold; margin-bottom: 20px; letter-spacing: 3px;">🧠 AI THERAPIST</div>
                        <span style="display: inline-block; background: rgba(255, 204, 0, 0.15); padding: 10px 30px; border-radius: 40px; font-size: 38px; margin-bottom: 20px; color: #ffcc00; border: 2px solid rgba(255, 204, 0, 0.3);">{emoji} {emotion_tag}</span>
                        <div style="font-size: 52px; font-weight: bold; margin-top: 15px; line-height: 1.4;">{response_text}</div>
                    </div>
                """
            else:
                chat_html = f"""
                    <div style="background: linear-gradient(135deg, #0a2a4a 0%, #0d3b66 100%); padding: 50px 55px; border-radius: 24px; margin: 25px 0; border-left: 10px solid #00ff88; color: #ffffff; text-align: center; box-shadow: 0 12px 48px rgba(0, 255, 136, 0.2);">
                        <div style="color: #00ff88; font-size: 36px; font-weight: bold; margin-bottom: 20px; letter-spacing: 3px;">🧠 AI THERAPIST</div>
                        <div style="font-size: 52px; font-weight: bold; margin-top: 15px; line-height: 1.4;">{raw}</div>
                    </div>
                """
            therapist_placeholder.markdown(chat_html, unsafe_allow_html=True)

        # Listening indicator at bottom
        listen_placeholder.markdown(f"""
            <div class="listening-indicator">
                {'🎤 <b>LISTENING...</b> - Speak naturally, the AI is analyzing your emotions' if speaking else '🔇 <b>Waiting for you to speak...</b> - I am monitoring your emotions in real-time'}
            </div>
        """, unsafe_allow_html=True)

        frame_count += 1
        time.sleep(0.05)

    voice_running[0] = False
    cap.release()
    st.success("✅ Session ended.")
