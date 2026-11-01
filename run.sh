#!/bin/bash
PYTHONPATH=backend backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

