# 📦 Kit Deployment & Testing Guide

This guide provides the step-by-step instructions to run, test, and validate the **Multimodal Emotion Monitoring System** on your hardware kit.

---

## 1. Environment Setup

Before running the system, ensure your hardware kit (Jetson/NUC/PC) is prepared.

### 🛠️ System Prerequisites (Linux)
Install the necessary system libraries for audio and serial communication:
```bash
sudo apt-get update
sudo apt-get install libasound-dev portaudio19-dev python3-dev
```

### 📦 Install Python Dependencies
Run this in the project root:
```bash
pip install -r requirements.txt
```

### 🔑 API Configuration
1.  Copy `.env.example` to `.env`.
2.  Open `.env` and enter your **GROQ_API_KEY**.
    *   *Note: If you don't have a key, the system will run in "Mock AI" mode, which is fine for initial hardware validation.*
3.  Verify the `SERIAL_PORT` (usually `/dev/ttyUSB0` or `/dev/ttyACM0`).

---

## 2. Hardware Diagnostic Suite

If you want to test the camera, audio, or system health specifically, run:
```bash
python3 tests/hardware_tests/run_all_tests.py
```

---

## 3. Running the Sensing Hub

Start the master orchestrator to begin multimodal capture:
```bash
python3 main.py
```

You should see 4 success messages in the terminal:
- `[Thread] Video Modality Started`
- `[Thread] Voice Modality Started`
- `[Thread] Biometric Modality Started`
- `[Thread] AI Fusion Engine Started`

---

## 3. Testing & Validation Steps

To ensure the kit is working correctly, perform these four validation checks:

### ✅ CHECK 1: Video Modality (Camera)
- **Action:** Wave your hand or move your face in front of the kit's camera.
- **Validation:** Observe the terminal output. It should toggle between `Interested`, `Focused/Distressed`, or `Bored/Not Present` based on movement/face proximity.

### ✅ CHECK 2: Voice Modality (Microphone)
- **Action:** Speak loudly into the HMD or kit microphone.
- **Validation:** The "Voice Arousal" log in the terminal should change from `Low/Silent` to `High (Speaking/Anxious)` during speech.

### ✅ CHECK 3: Biometric Modality (Serial)
- **Action:** Place your finger on the PPG heart rate sensor.
- **Validation:** If the sensor is connected, the `HR` (Heart Rate) values should stabilize between 60-100 BPM. If not connected, the terminal will report `Running in MOCK biometric mode` with fluctuating values.

### ✅ CHECK 4: AI Fusion & Logic (LLM)
- **Action:** Provide simultaneous high inputs (Speak loudly + move closer to camera).
- **Validation:** The `-- [LIVE RECOMMENDATION] --` JSON should reflect a high "distress" score and suggest an environmental change like `"Switch to relaxing room"`.

---

---

## 🛑 Troubleshooting

- **"Permission Denied" on Serial:** Run `sudo usermod -a -G dialout $USER` then restart.
- **"Audio Device Not Found":** Ensure your HMD is set as the default input device in Linux Sound Settings.
- **"Latency Issues":** The LLM fusion is set to poll every 5 seconds to avoid rate limits; this is intentional for therapy stability.
