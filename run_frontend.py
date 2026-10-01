"""
Direct entrypoint to launch the Streamlit frontend from VS Code or terminal.
Right-click and select 'Run Python File in Terminal' or run via terminal.
"""

import os
import sys
import subprocess

# Ensure working directory is project root
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
os.chdir(ROOT_DIR)

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🚀 Starting Streamlit Quality Intelligence Cockpit")
    print("📍 Local URL: http://localhost:8501")
    print("="*70 + "\n")
    
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        "app/streamlit_app.py",
        "--server.port=8501",
        "--server.address=localhost"
    ]
    subprocess.run(cmd)
