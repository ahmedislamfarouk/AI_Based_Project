#!/bin/bash
# AI Therapist — Microservice Build & Deploy
# Run from: /home/skyvision/AI_Based_Project
set -e

BASE_IMAGE="ai-therapist-base:latest"

echo "==================================================================="
echo "  AI Therapist — Microservice Docker Build"
echo "==================================================================="
echo ""

# Step 1: Build base image (heavy deps — do once, takes ~20-30 min)
if [[ "$1" == "--base" ]] || ! docker image inspect "$BASE_IMAGE" &>/dev/null; then
    echo "[1/3] Building base image with ALL dependencies (PyTorch, TF, DeepFace, etc.)..."
    echo "      This takes 20-30 min but only needs to be done ONCE."
    docker build -t "$BASE_IMAGE" -f Dockerfile.base .
    echo "      Base image built: $BASE_IMAGE"
else
    echo "[1/3] Base image '$BASE_IMAGE' already exists. Skipping."
    echo "      Rebuild with: $0 --base"
fi
echo ""

# Step 2: Build microservices (fast — just copies code, seconds each)
echo "[2/3] Building microservice images (fast COPY only)..."
docker compose build
echo ""

# Step 3: Start services
echo "[3/3] Starting all services..."
docker compose up -d
echo ""

echo "==================================================================="
echo "  All services starting! Wait ~60s for model loading..."
echo ""
echo "  Services:"
echo "    Web UI:    http://localhost:8010"
echo "    Face API:  http://localhost:8001/health"
echo "    Voice API: http://localhost:8002/health"
echo "    Fusion API: http://localhost:8003/health"
echo ""
echo "  Useful commands:"
echo "    docker compose logs -f              # all logs"
echo "    docker compose logs -f web-api      # web API logs"
echo "    docker compose logs -f fusion-llm   # LLM logs"
echo "    docker compose restart web-api      # restart just the API"
echo "    docker compose down                 # stop everything"
echo "    docker compose up -d --build web-api  # rebuild & restart just API"
echo "==================================================================="
