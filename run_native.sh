#!/bin/bash
# Start the AI Therapist web app natively (no Docker)
# Run from: /home/skyvision/AI_Based_Project

cd /home/skyvision/AI_Based_Project
echo "Starting AI Therapist on http://localhost:8080 ..."
python3 -u -m uvicorn web_app:app --host 0.0.0.0 --port 8080
