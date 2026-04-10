# 🧠 AI Multimodal Emotion Monitor & Therapist

An AI-powered real-time emotion monitoring and therapy system that uses **DeepFace**, **MediaPipe**, and **LLMs** to analyze facial expressions, voice arousal, and biometric data. It features a live Streamlit dashboard that acts as an interactive AI therapist.

---

## 🚀 Quick Start (Laptop / PC)

### 1. Run with Docker (Recommended)
The easiest way to run the system is via Docker. This includes all dependencies (DeepFace, MediaPipe, LLM clients).

```bash
# Build and start the Streamlit dashboard
docker-compose up -d

# Open the dashboard in your browser
http://localhost:8501
```

**Note:** If you encounter network errors, run in host mode:
```bash
docker run -d --name emotion-monitor --network host \
  --device=/dev/video0:/dev/video0 \
  --device=/dev/snd:/dev/snd \
  ai-based-ai-based-system:latest \
  streamlit run live_dashboard.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
```

### 2. Run Locally (Python)
If you prefer not to use Docker:

```bash
pip install -r requirements.txt
streamlit run live_dashboard.py
```

---

## 📦 Maven Kit Deployment (Offline / Slow Wi-Fi)

Since the AI models (DeepFace, MediaPipe) are large (~2GB), it is highly recommended to build the Docker image on a fast machine and transfer it to the Maven Kit via USB.

### Step 1: Build and Export (On Laptop)
```bash
# 1. Build the image
docker-compose build

# 2. Export to a compressed tar file
docker save ai-based-ai-based-system:latest | gzip > emotion-monitor.tar.gz
```
*This creates a file `emotion-monitor.tar.gz` (~4-5GB).*

### Step 2: Transfer to Maven Kit
Copy `emotion-monitor.tar.gz` to the Maven Kit via USB drive or SCP.

### Step 3: Import and Run (On Maven Kit)
```bash
# 1. Load the image
docker load < emotion-monitor.tar.gz

# 2. Run the system (with hardware passthrough if sensors are connected)
docker run -d --name emotion-monitor \
  --network host \
  --device=/dev/video0:/dev/video0 \
  --device=/dev/snd:/dev/snd \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  ai-based-ai-based-system:latest \
  streamlit run live_dashboard.py --server.port 8501 --server.address 0.0.0.0 --server.headless true

# 3. Access the dashboard
# On the Kit's display: http://localhost:8501
# Or from another PC: http://<KIT_IP_ADDRESS>:8501
```

---

##  Features

- **️ Real-Time Emotion Detection:** Uses DeepFace and MediaPipe to detect 7 emotions (Happy, Sad, Angry, Fear, Surprise, Disgust, Neutral) plus fatigue states (Drowsiness, Yawning, Head Nodding).
- **🎤 Voice Analysis:** Monitors microphone input to detect speaking patterns and arousal levels.
- **🤖 AI Therapist:** A built-in LLM agent (Groq/Local) analyzes your emotional state and provides real-time, empathetic text recommendations.
- **📊 Live Dashboard:** A Streamlit-based UI showing camera feed, emotion timeline, and therapist chat.
- **📦 Hardware Ready:** Configured for Jetson/Raspberry Pi with support for USB cameras, microphones, and serial biometric sensors.

---

## ⚙️ Configuration

Create a `.env` file in the root directory:

```bash
GROQ_API_KEY=your_groq_api_key_here
NEWS_API_KEY=your_news_api_key_here
```

- **`GROQ_API_KEY`**: Required for the LLM therapist to generate smart recommendations.
- **`NEWS_API_KEY`**: Optional, used by the RAG system.
- If no API key is provided, the system runs in "Mock Mode" with pre-written therapist responses.

---

## 🛠️ Project Structure

- `live_dashboard.py`: Main Streamlit application (AI Therapist UI).
- `main.py`: Background orchestrator (Video, Voice, Biometrics, Fusion).
- `core/model/inference.py`: LLM Fusion Agent.
- `core/rag/`: RAG system for knowledge retrieval.
- `Emotion Detection/`: DeepFace-based emotion analysis engine.
- `modules/`: Hardware interfaces (Video, Voice, Biometrics, Output).

---

## 📜 License

Proprietary - All rights reserved.
