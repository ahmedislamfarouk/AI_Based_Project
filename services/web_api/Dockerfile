FROM ai-therapist-base:latest
WORKDIR /app
COPY modules/ modules/
COPY services/web_api/service.py service.py
COPY static/ static/
EXPOSE 8010
CMD ["python", "service.py"]
