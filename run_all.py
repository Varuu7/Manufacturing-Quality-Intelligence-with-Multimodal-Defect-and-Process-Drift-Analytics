"""
Unified Launcher for Manufacturing Quality Intelligence System
Starts both FastAPI backend (:8000) and Streamlit frontend (:8501) concurrently.
"""

import os
import sys
import subprocess
import time

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
os.chdir(ROOT_DIR)

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🏭 Starting Manufacturing Quality Intelligence System (BDS-27)")
    print("📍 Frontend Dashboard:  http://localhost:8501")
    print("📍 Backend REST API:    http://127.0.0.1:8000")
    print("📖 Swagger Docs:        http://127.0.0.1:8000/docs")
    print("📖 Redoc UI:            http://127.0.0.1:8000/redoc")
    print("="*70 + "\n")

    # Start FastAPI Backend
    print("⏳ Starting FastAPI Backend on port 8000...")
    backend_proc = subprocess.Popen([sys.executable, "run_backend.py"])
    time.sleep(2)

    # Start Streamlit Frontend
    print("⏳ Starting Streamlit Frontend on port 8501...")
    frontend_proc = subprocess.Popen([sys.executable, "run_frontend.py"])

    print("\n✅ Both services are now running! Press Ctrl+C in this terminal to shut down.\n")

    try:
        backend_proc.wait()
        frontend_proc.wait()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down backend and frontend services...")
        backend_proc.terminate()
        frontend_proc.terminate()
        print("✅ All services stopped successfully.")
