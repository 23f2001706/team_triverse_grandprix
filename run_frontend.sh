#!/bin/bash
# Start the Gradio frontend
cd frontend
export BACKEND_URL="http://localhost:8000"
python app.py
