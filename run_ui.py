#!/usr/bin/env python3
"""SilverForge UI 실행 스크립트

Usage:
    python run_ui.py          # Streamlit UI 실행 (기본)
    python run_ui.py --api    # FastAPI 서버 실행
"""

import sys
import subprocess
from pathlib import Path


def run_streamlit():
    """Streamlit UI 실행"""
    app_path = Path(__file__).parent / "silverforge" / "app.py"
    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        str(app_path),
        "--server.port=8501",
        "--server.headless=true",
    ])


def run_api():
    """FastAPI 서버 실행"""
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "silverforge.api:app",
        "--host=0.0.0.0",
        "--port=8000",
        "--reload",
    ])


if __name__ == "__main__":
    if "--api" in sys.argv:
        print("🚀 Starting FastAPI server at http://localhost:8000")
        print("📖 API docs: http://localhost:8000/docs")
        run_api()
    else:
        print("🔥 Starting SilverForge UI at http://localhost:8501")
        run_streamlit()
