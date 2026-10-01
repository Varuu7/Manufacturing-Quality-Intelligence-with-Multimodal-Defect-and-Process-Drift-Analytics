@echo off
title Manufacturing Quality Intelligence - Streamlit Cockpit (:8501)
cd /d "%~dp0"
echo Starting Streamlit Dashboard on http://localhost:8501 ...
python run_frontend.py
pause
