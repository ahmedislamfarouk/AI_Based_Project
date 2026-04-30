FROM ai-therapist-base:latest
WORKDIR /app
COPY core/ core/
COPY modules/output/ modules/output/
COPY services/fusion_llm/service.py service.py
COPY LLM/ LLM/
COPY models/ models/
EXPOSE 8003
CMD ["python", "service.py"]
