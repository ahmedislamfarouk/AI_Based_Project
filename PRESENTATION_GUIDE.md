# 🧠 AI Multimodal Emotion Monitor & Therapist - Project Guide

This document outlines the core concepts of our project and provides a structured plan for team presentation and future development.

---

## 📖 Project Overview

**One-Sentence Summary:**
A real-time AI system that acts as a personal therapist by monitoring your face (DeepFace), voice (PyAudio), and biometrics to detect emotional distress and provide instant, empathetic support via a chat interface.

---

## 👥 Team Breakdown (5 Members)

To present the project effectively, we have divided the workload into 5 distinct roles:

| Member | Role Title | Responsibilities (Presentation Focus) |
| :--- | :--- | :--- |
| **1** | **System Architect** | **Introduction & High-Level Design.** Explains the problem (mental health monitoring), the solution, and how the 4 modules (Vision, Voice, Biometrics, LLM) connect together. |
| **2** | **Computer Vision Lead** | **Emotion & Fatigue Detection.** Explains the **DeepFace** and **MediaPipe** models from the `Emotion Detection` folder. Demonstrates how it detects "Sad", "Happy", "Yawning", and "Drowsiness". |
| **3** | **AI & LLM Engineer** | **The "Brain" (Therapist).** Explains how the **Fusion Agent** takes raw emotions, combines them with voice data, and asks the LLM (Groq) to generate a caring response. |
| **4** | **Voice & Hardware Engineer** | **Audio & Biometrics.** Explains how the microphone detects "Voice Arousal" (shouting vs. quiet) and how the system is designed to read heart rate sensors (MAX30100) via Serial Port. |
| **5** | **DevOps & Deployment Lead** | **Docker & UI.** Explains how the **Streamlit Dashboard** works and demonstrates **Dockerization**—how the heavy AI models are packaged to run instantly on the Maven Kit or any laptop. |

---

## 🎤 Presentation Strategy

### 1. How to Present "Dockerization"
*   **The Problem:** "Our AI models (DeepFace, MediaPipe) require heavy dependencies (TensorFlow, OpenCV). Installing this manually on a device like the Maven Kit takes hours and often fails due to errors."
*   **The Solution:** "We created a Docker container that acts like a **virtual computer**. It comes pre-installed with all 2GB of AI models. When the Maven Kit boots up, it doesn't need to install anything—it just runs our container, and the system starts in 5 seconds."

### 2. How to Present "Connections"
Draw a simple flow chart on your slide:
`[Camera/Mic]` → `[Sensing Modules]` → `[Fusion Agent]` → `[LLM Therapist]` → `[User Screen]`
*   **Camera** sees a "Sad" face.
*   **Mic** hears a "Low/Quiet" voice.
*   **Fusion Agent** calculates: "Sad Face + Quiet Voice = High Risk of Depression."
*   **LLM** generates response: "You seem a bit down today. Would you like to talk about it?"

---

## 🛠️ Technical Status & Future Work

### ✅ What is Fixed & Working
1.  **Real Emotion Model:** The system now uses the **DeepFace** and **MediaPipe** models from the `Emotion Detection` folder (not just simple face boxes).
2.  **Therapist Chat:** The LLM analyzes emotions every 10 seconds (to avoid spamming).
3.  **Streamlit UI:** The dashboard launches automatically and shows a live camera feed with emotion overlays.

### 🚀 Future Work
1.  **Talking Therapist:** We have a `tts_engine.py` module. We can enable this so the therapist **speaks** the recommendation out loud instead of just text.
2.  **Heart Rate Integration:** The code for `BiometricProcessor` is written. It is ready to read data from a MAX30100 sensor connected to the USB port.
3.  **Laptop Optimization:** Currently, the system is heavy for laptops. We can optimize the model loading speed.

---

## 📜 License
Proprietary - All rights reserved.
