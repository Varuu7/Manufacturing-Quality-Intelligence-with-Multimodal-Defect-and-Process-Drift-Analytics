"""
Direct entrypoint to run the FastAPI backend from VS Code or terminal.
Right-click and select 'Run Python File in Terminal' or press F5.
"""

import sys
import os
import uvicorn

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🚀 Starting Manufacturing Quality Intelligence REST API")
    print("📍 Local URL:     http://127.0.0.1:8000")
    print("📖 Swagger Docs:  http://127.0.0.1:8000/docs")
    print("📖 Redoc UI:      http://127.0.0.1:8000/redoc")
    print("="*70 + "\n")
    
    uvicorn.run("src.api.main:app", host="127.0.0.1", port=8000, reload=True)
