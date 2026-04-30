FROM ai-therapist-base:latest
WORKDIR /app
COPY services/face_analysis/service.py service.py
EXPOSE 8001
CMD ["python", "service.py"]
