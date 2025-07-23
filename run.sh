#!/bin/bash

# Load environment variables from .env (optional)
export $(grep -v '^#' .env | xargs)


#!/bin/bash

echo "[*] Starting FastAPI server..."
uvicorn app.main:app --host 0.0.0.0 --port 8001 &

echo "[*] Starting ARI service..."
python3 -m app.services.ari_service
