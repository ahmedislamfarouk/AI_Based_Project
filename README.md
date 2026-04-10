# Emotion-Adaptive VR Therapy Platform

A multimodal emotion monitoring system that analyzes video, voice, and biometric data to provide real-time intervention recommendations using AI fusion and RAG.

## Features

- **Multimodal Emotion Detection**: Video facial expressions, voice arousal, biometric signals
- **AI Fusion Agent**: LLM-powered distress level assessment (0-100 scale)
- **RAG Knowledge Base**: Vector database for context-aware recommendations
- **TTS Output**: Voice alerts for high distress situations
- **Session Logging**: Persistent event logging for analysis
- **Hardware Integration**: Camera, microphone, MAX30100 heart rate sensor, EDA

## Quick Start with Docker

### Prerequisites
- Docker and Docker Compose installed
- GROQ_API_KEY (get from https://console.groq.com/)
- Hardware sensors connected (optional - system runs in mock mode without them)

### Setup

1. **Configure Environment Variables**:
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys
   ```

2. **Build and Run**:
   ```bash
   docker-compose up --build
   ```

3. **Stop the System**:
   ```bash
   docker-compose down
   ```

### Running on Maven Kit

To deploy on your Maven Kit system:

```bash
# Build the Docker image
docker-compose build

# Save the image to a tar file
docker save emotion-monitor:latest | gzip > emotion-monitor.tar.gz

# Transfer to Maven Kit
scp emotion-monitor.tar.gz user@maven-kit:/path/to/destination

# On Maven Kit, load the image
docker load < emotion-monitor.tar.gz

# Run
docker-compose up -d
```

## Local Development (Without Docker)

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Configure
```bash
cp .env.example .env
# Edit .env with your API keys and hardware settings
```

### Run
```bash
python main.py
```

### Run Dashboard (Optional)
```bash
streamlit run dashboard.py
```

## Architecture

```
┌─────────────┐  ┌──────────────┐  ┌───────────────┐
│   Video     │  │    Voice     │  │  Biometrics   │
│  Emotion    │  │   Emotion    │  │ Heart Rate    │
│  Analyzer   │  │   Analyzer   │  │ & EDA         │
└──────┬──────┘  └──────┬───────┘  └───────┬───────┘
       │                │                   │
       └────────────────┼───────────────────┘
                        │
                 ┌──────▼──────┐
                 │   Fusion    │
                 │   Agent     │
                 │  (LLM)      │
                 └──────┬──────┘
                        │
           ┌────────────┼────────────┐
           │            │            │
      ┌────▼───┐  ┌─────▼────┐  ┌───▼────┐
      │  TTS   │  │ Session  │  │  RAG   │
      │ Engine │  │ Logger   │  │ DB     │
      └────────┘  └──────────┘  └────────┘
```

## Configuration

See `.env.example` for available options:

- `GROQ_API_KEY`: Groq API key for LLM inference
- `NEWS_API_KEY`: For RAG knowledge base (optional)
- `SERIAL_PORT`: Serial port for biometric sensor
- `CAMERA_ID`: Camera device ID
- `AUDIO_CHANNELS`: Number of audio channels

## RAG System

The RAG (Retrieval-Augmented Generation) system uses ChromaDB to index and retrieve relevant mental health articles. To populate the knowledge base:

```python
from core.rag import KnowledgeRetriever

retriever = KnowledgeRetriever()
retriever.fetch_and_index_news(topic="mental health", max_articles=10)
context = retriever.retrieve_context("anxiety treatment")
```

## Project Structure

```
├── main.py                 # Main entry point
├── dashboard.py            # Streamlit dashboard
├── core/
│   ├── model/             # AI fusion agent
│   └── rag/               # RAG system (vector DB + retriever)
├── modules/
│   ├── video/             # Video emotion analysis
│   ├── voice/             # Voice emotion analysis
│   ├── biometrics/        # Biometric signal processing
│   └── output/            # TTS, logging, speakers
├── configs/               # Configuration files
├── data/                  # Data storage
│   ├── raw/               # Raw sensor data
│   └── processed/         # Processed data & vector DB
└── requirements.txt       # Python dependencies
```

## Troubleshooting

### No GROQ_API_KEY
System runs in mock mode with default recommendations.

### Hardware Not Found
Sensors are optional. System will log errors but continue running.

### Port Conflicts
Change Streamlit port in docker-compose.yml if 8501 is in use.

## License

Proprietary - All rights reserved
