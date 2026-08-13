#!/bin/bash
# Start the FastAPI backend
cd backend
export HF_TOKEN="your_hf_token_here"  # Replace with your token
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
