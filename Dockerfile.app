FROM ai-therapist-base:latest

COPY . /app

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "web_app:app", "--host", "0.0.0.0", "--port", "8000"]
