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
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy main requirements first
COPY requirements.txt .

# Install only CPU versions to keep image small
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p data/processed data/raw logs LLM/books LLM/faiss_index LLM/model

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose ports (Streamlit dashboard if used)
EXPOSE 8501

# Default command
CMD ["python", "main.py"]
