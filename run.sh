#!/bin/bash

# Load environment variables from .env (optional)
export $(grep -v '^#' .env | xargs)

# Run the FastAPI server with hot reload on port 8000
uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000} --reload
