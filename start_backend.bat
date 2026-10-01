@echo off
title Manufacturing Quality Intelligence - FastAPI Backend (:8000)
cd /d "%~dp0"
echo Starting FastAPI Backend on http://127.0.0.1:8000 ...
python run_backend.py
pause
