FROM nvidia/cuda:12.2.2-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120

RUN apt-get update && apt-get install -y \
    python3.11 python3.11-venv python3-pip python3.11-dev \
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
    make \
    cmake \
    ninja-build \
    pkg-config \
    git \
    libegl1 \
    libegl-mesa0 \
    libglvnd0 \
    libgl1-mesa-glx \
    libgles2-mesa \
    libgomp1 \
    libopengl0 \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

COPY requirements.txt .

RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel && \
    python -m pip install --no-cache-dir \
        torch torchvision torchaudio \
        --index-url https://download.pytorch.org/whl/cu121 && \
    python -m pip install --no-cache-dir --prefer-binary -r requirements.txt && \
    python -m pip install --no-cache-dir --prefer-binary safetensors

# Patch transformers to bypass torch<2.6 security check (safe for trusted model files)
COPY scripts/patch_transformers.py /tmp/patch_transformers.py
RUN python /tmp/patch_transformers.py && rm /tmp/patch_transformers.py

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
ENV TF_CPP_MIN_LOG_LEVEL=3

# Expose ports (FastAPI web app)
EXPOSE 8000

# Use entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command
CMD ["uvicorn", "web_app:app", "--host", "0.0.0.0", "--port", "8000"]