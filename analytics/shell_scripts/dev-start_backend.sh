#!/bin/bash

# -----------------------------------------
# Dev Backend Starter Script
# Location: /var/www/cgh
# -----------------------------------------

set -euo pipefail

# Define fixed Dev paths
PROJECT_DIR="/var/www/cgh"
ENV_FILE="$PROJECT_DIR/.env"
VENV_DIR="$PROJECT_DIR/venv"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/backend.log"

echo "===== Starting FastAPI Backend (DEV) ====="

# -----------------------------------------
# Create logs directory
# -----------------------------------------
mkdir -p "$LOG_DIR"
touch "$LOG_FILE"

echo "Log file: $LOG_FILE"
echo "---------------------------------" >> "$LOG_FILE"
echo "$(date) - Backend startup initiated" >> "$LOG_FILE"

# -----------------------------------------
# Navigate to project folder
# -----------------------------------------
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Backend folder not found: $PROJECT_DIR"
    exit 1
fi

cd "$PROJECT_DIR"
echo "✅ Changed directory to $PROJECT_DIR" | tee -a "$LOG_FILE"

# -----------------------------------------
# Load environment variables
# -----------------------------------------
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ .env file not found at $ENV_FILE" | tee -a "$LOG_FILE"
    exit 1
fi

set -a
source "$ENV_FILE"
set +a

echo "✅ Environment variables loaded" | tee -a "$LOG_FILE"

# -----------------------------------------
# Validate env variables
# -----------------------------------------
if [ -z "${BACKEND_PORT:-}" ]; then
    echo "❌ BACKEND_PORT is not set" | tee -a "$LOG_FILE"
    exit 1
fi

if [ -z "${BACKEND_URL:-}" ]; then
    echo "❌ BACKEND_URL is not set" | tee -a "$LOG_FILE"
    exit 1
fi

echo "Backend port: $BACKEND_PORT" | tee -a "$LOG_FILE"
echo "Backend URL : $BACKEND_URL"  | tee -a "$LOG_FILE"

# -----------------------------------------
# Setup virtual environment (Reuse existing)
# -----------------------------------------
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..." | tee -a "$LOG_FILE"
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
echo "Using Python: $(which python3)" | tee -a "$LOG_FILE"
python3 --version | tee -a "$LOG_FILE"

# -----------------------------------------
# Install dependencies
# -----------------------------------------
echo "Installing dependencies..." | tee -a "$LOG_FILE"
pip install --upgrade pip >> "$LOG_FILE" 2>&1
pip install -r requirements.txt >> "$LOG_FILE" 2>&1

echo "✅ Dependencies installed" | tee -a "$LOG_FILE"

# -----------------------------------------
# Stop process running on port
# -----------------------------------------
EXISTING_PID=$(lsof -ti tcp:$BACKEND_PORT || true)

if [ -n "$EXISTING_PID" ]; then
    echo "Stopping existing PID: $EXISTING_PID" | tee -a "$LOG_FILE"
    kill -9 $EXISTING_PID
    sleep 2
else
    echo "No existing process on port $BACKEND_PORT" | tee -a "$LOG_FILE"
fi

# -----------------------------------------
# Build Frontend
# -----------------------------------------
FRONTEND_DIR="$PROJECT_DIR/frontend"

if [ ! -d "$FRONTEND_DIR" ]; then
    echo "❌ Frontend folder not found: $FRONTEND_DIR" | tee -a "$LOG_FILE"
    exit 1
fi

echo "Building frontend..." | tee -a "$LOG_FILE"
cd "$FRONTEND_DIR"

npm install >> "$LOG_FILE" 2>&1
npm run build >> "$LOG_FILE" 2>&1

echo "✅ Frontend build completed" | tee -a "$LOG_FILE"

# Go back to backend root
cd "$PROJECT_DIR"


# -----------------------------------------
# Start FastAPI Backend
# -----------------------------------------
echo "Starting FastAPI backend..." | tee -a "$LOG_FILE"

nohup python3 -m uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port "$BACKEND_PORT" \
  --log-level debug \
  >> "$LOG_FILE" 2>&1 &

sleep 5

# -----------------------------------------
# Verify startup
# -----------------------------------------
NEW_PID=$(lsof -ti tcp:$BACKEND_PORT || true)

if [ -n "$NEW_PID" ]; then
    echo "✅ FastAPI started successfully (PID: $NEW_PID)" | tee -a "$LOG_FILE"
else
    echo "❌ FastAPI failed to start. Check logs: $LOG_FILE" | tee -a "$LOG_FILE"
fi

echo "Access URL: $BACKEND_URL" | tee -a "$LOG_FILE"
echo "===== Startup Complete (DEV) =====" | tee -a "$LOG_FILE"
