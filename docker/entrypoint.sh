#!/bin/bash
cd /app
if [ "$API_ENABLED" == "yes" ]; then
    uvicorn app_api:app --port ${API_PORT:-8080} --no-access-log --host 0.0.0.0
else
    python api_noapi.py
fi