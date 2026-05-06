#!/bin/bash
# AI Therapist — Microservice Build & Deploy
# Run from: /home/skyvision/AI_Based_Project
set -e

BASE_IMAGE="ai-therapist-base:latest"

echo "==================================================================="
echo "  AI Therapist — Microservice Docker Build & Deploy"
echo "==================================================================="
echo ""

# Step 0: Aggressive & Intelligent Cleanup
echo "[0/4] Cleaning up existing containers and clearing locks..."
set +e # Temporarily disable exit-on-error
docker compose down
DOWN_STATUS=$?

# If the normal shutdown failed (e.g., permission denied)
if [ $DOWN_STATUS -ne 0 ]; then
    echo "      Warning: Containers are stuck. Force restarting Docker daemon..."
    sudo systemctl restart docker
    sleep 3
    
    echo "      Retrying container teardown..."
    docker compose down
    RETRY_STATUS=$?
    
    # If the daemon restart STILL didn't fix it, go nuclear (Kill -9)
    if [ $RETRY_STATUS -ne 0 ]; then
        echo "      CRITICAL: Daemon restart failed. Locks are deeply stuck."
        echo "      Initiating intelligent PID detection and termination..."
        
        # Get all container IDs associated with this compose project
        # Fallback to grepping the project name if compose ps fails
        CONTAINER_IDS=$(docker compose ps -a -q)
        if [ -z "$CONTAINER_IDS" ]; then
            CONTAINER_IDS=$(docker ps -a -q -f "name=ai_based_project")
        fi

        if [ -n "$CONTAINER_IDS" ]; then
            for CID in $CONTAINER_IDS; do
                echo "      -> Inspecting stuck container: $CID"
                
                # Extract the host-level Process ID (PID)
                PID=$(docker inspect -f '{{.State.Pid}}' "$CID" 2>/dev/null)
                
                # If PID exists and is greater than 0, assassinate it
                if [ -n "$PID" ] && [ "$PID" -gt 0 ]; then
                    echo "         Executing sudo kill -9 on Host PID: $PID"
                    sudo kill -9 "$PID" 2>/dev/null || true
                fi
                
                # Force remove the container shell
                echo "         Force removing container artifact: $CID"
                docker rm -f "$CID" 2>/dev/null || true
            done
        else
            echo "      No stray containers found to kill."
        fi
        
        # Final pass to clear out orphaned networks and volumes
        echo "      Executing final compose network cleanup..."
        docker compose down
    fi
fi
set -e # Re-enable exit-on-error
echo "      Cleanup complete."
echo ""

# Step 1: Build base image (heavy deps — do once, takes ~20-30 min)
if [[ "$1" == "--base" ]] || ! docker image inspect "$BASE_IMAGE" &>/dev/null; then
    echo "[1/4] Building base image with ALL dependencies (PyTorch, TF, DeepFace, etc.)..."
    echo "      This takes 20-30 min but only needs to be done ONCE."
    docker build -t "$BASE_IMAGE" -f Dockerfile.base .
    echo "      Base image built: $BASE_IMAGE"
else
    echo "[1/4] Base image '$BASE_IMAGE' already exists. Skipping."
    echo "      Rebuild with: $0 --base"
fi
echo ""

# Step 2: Build microservices (fast — just copies code, seconds each)
echo "[2/4] Building microservice images (fast COPY only)..."
docker compose build
echo ""

# Step 3: Start services
echo "[3/4] Starting all services..."
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
echo "    docker compose logs -f                # all logs"
echo "    docker compose logs -f web-api        # web API logs"
echo "    docker compose logs -f fusion-llm     # LLM logs"
echo "    docker compose restart web-api        # restart just the API"
echo "    docker compose down                   # stop everything"
echo "    docker compose up -d --build web-api  # rebuild & restart just API"
echo "==================================================================="