FROM ai-therapist-base:latest
WORKDIR /app
COPY modules/ modules/
COPY models/ models/
COPY services/voice_analysis/service.py service.py
EXPOSE 8002
CMD ["python", "service.py"]
