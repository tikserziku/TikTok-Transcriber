#!/bin/bash
export PORT=${PORT:-8000}
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:$PORT
