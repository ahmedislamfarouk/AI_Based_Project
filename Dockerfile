FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libsndfile1 \
    portaudio19-dev \
    libpulse-dev \
    libasound2-dev \
    libusb-1.0-0 \
    ffmpeg \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy main requirements first
COPY requirements.txt .

# Install GPU-enabled PyTorch (CUDA 12.1) and dependencies
RUN pip install --no-cache-dir \
    torch torchvision torchaudio && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p data/processed data/raw logs LLM/books LLM/faiss_index LLM/model

# Copy and set up entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose ports (FastAPI web app)
EXPOSE 8000

# Use entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command
CMD ["uvicorn", "web_app:app", "--host", "0.0.0.0", "--port", "8000"]
