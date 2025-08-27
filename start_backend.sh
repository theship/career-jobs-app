#!/bin/bash
# Load environment variables and start backend
set -a
source .env
set +a
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000