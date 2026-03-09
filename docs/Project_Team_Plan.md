# Updated Project Team Plan: Emotion-Adaptive VR Therapy Platform

This plan outlines the distribution of tasks for a 5-member team. The project focuses on a multimodal (Voice, Biometric, Video) AI system integrated with an LLM and deployed on a portable kit for VR therapy.

---

## 👥 Team Structure & Role Breakdown

### 1. Vocal Intelligence Lead (Member 1)
**Focus:** Audio capture from the HMD microphone and acoustic emotion classification.
- **Key Tasks:**
    - Implement real-time audio streaming from the VR headset microphone.
    - Develop the **Mel-Spectrogram** generation pipeline (STFT).
    - Deploy a pre-trained voice emotion model (arousal/valence detection).
    - Ensure noise cancellation features to filter out VR environment sounds.
- **Reference Files:** `modules/voice/`

### 2. Biometric Engineering Lead (Member 2)
**Focus:** Wearable sensors (EDA/PPG) and physiological feature extraction.
- **Key Tasks:**
    - Finalize the `sensor_reader.ino` for the Handback sensors.
    - Implement the **2D Scalogram** (CWT) transformation for physiological signals.
    - Synchronize biometric data timestamps with the other modalities.
    - Filter movement artifacts from the PPG (heart rate) signal.
- **Reference Files:** `hardware/`, `modules/biometrics/`

### 3. Visual Emotion Developer (Member 3)
**Focus:** Face/Body analysis via the kit's camera system.
- **Key Tasks:**
    - Implement real-time video capture using the kit's integrated camera or HMD face-cam.
    - Develop the pipeline for **Facial Expression Recognition (FER)** using 2D CNNs.
    - Extract distress markers (e.g., eye squinting, lip tension) from video frames.
    - Optimize the video model to run efficiently on the kit's hardware (e.g., using ONNX or TensorRT).
- **Reference Files:** `modules/video/`

### 4. LLM & Cognitive Reasoning Architect (Member 4)
**Focus:** The "Virtual Therapist" brain and multimodal decision-making.
- **Key Tasks:**
    - Build the **Fusion Engine**: Combining Voice, Biometric, and Video scores into a unified "Distress Level."
    - Integrate the Large Language Model (e.g., Llama 3 or Gemma) to act as the orchestrator.
    - Develop internal reasoning logic: translating the fused emotion into therapeutic commands (e.g., "User is 80% anxious $\rightarrow$ Lower ambient volume").
    - Manage the prompt engineering for real-time NPC interaction.
- **Reference Files:** `core/model/`, `core/rag/`

### 5. System Integration & Kit Deployment Engineer (Member 5)
**Focus:** Hardware integration, WebSockets, and field-ready deployment.
- **Key Tasks:**
    - **Kit Integration:** Ensuring the Python AI pipeline runs stably on the portable compute unit (the "Kit").
    - Build the **WebSocket Server** to push commands from the AI brain to the VR Engine.
    - Develop the Master UI/Dashboard for the human therapist to monitor all 3 modalities live.
    - Packaging dependencies and managing the `main.py` execution lifecycle.
- **Reference Files:** `main.py`, `modules/output/`, `configs/`

---

## 🚀 Integration Workflow

| Step | Action | Responsibility |
| :--- | :--- | :--- |
| **1. Data Streams** | Parallel capture of Voice, Biometrics, and Video. | Members 1, 2, 3 |
| **2. Local Inference** | Modality-specific models generate emotion vectors. | Members 1, 2, 3 |
| **3. Fusion & Choice** | LLM digests all 3 vectors + context to decide action. | Member 4 |
| **4. VR Execution** | Commands sent via WebSocket to trigger VR changes. | Member 5 (+ VR Dev) |
| **5. Post-Analysis** | Save all logs to the Kit for therapist review. | Member 5 |

---

## 🛠️ Kit Integration Hardware Checklist
- [ ] **Compute:** Dedicated portable PC or Embedded Jetson/NUC.
- [ ] **Sensors:** Handback (Biometrics) + HMD (Voice) + External/Internal Camera (Video).
- [ ] **Networking:** Local ultra-low-latency router for WebSocket bridge.
- [ ] **Power:** Portable battery/distribution system for mobile therapy use.
