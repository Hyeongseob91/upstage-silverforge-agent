#!/usr/bin/env python3
"""SilverForge UI 실행 스크립트

Usage:
    python main.py          # Streamlit UI 실행 (기본)
    python main.py --api    # FastAPI 서버 실행
"""

import os
import sys
import subprocess
from pathlib import Path

# 프로젝트 루트 디렉토리
PROJECT_ROOT = Path(__file__).parent
SRC_DIR = PROJECT_ROOT / "src"


def get_venv_python() -> Path:
    """venv의 Python 인터프리터 경로 반환"""
    venv_path = PROJECT_ROOT / ".venv"

    if sys.platform == "win32":
        python_path = venv_path / "Scripts" / "python.exe"
    else:
        python_path = venv_path / "bin" / "python"

    if python_path.exists():
        return python_path

    return Path(sys.executable)


def check_dependencies(python_path: Path) -> bool:
    """필수 의존성 확인"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_DIR)

    result = subprocess.run(
        [str(python_path), "-c", "import streamlit; import silverforge"],
        capture_output=True,
        text=True,
        env=env,
    )
    return result.returncode == 0


def install_dependencies():
    """의존성 설치"""
    print("📦 의존성 설치 중...")
    subprocess.run(
        ["uv", "pip", "install", "-e", str(PROJECT_ROOT)],
        cwd=PROJECT_ROOT,
    )


def run_streamlit(python_path: Path):
    """Streamlit UI 실행"""
    app_path = SRC_DIR / "silverforge" / "app.py"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_DIR)

    subprocess.run(
        [
            str(python_path), "-m", "streamlit", "run",
            str(app_path),
            "--server.port=8502",
            "--server.headless=true",
        ],
        env=env,
        cwd=PROJECT_ROOT,
    )


def run_api(python_path: Path):
    """FastAPI 서버 실행"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_DIR)

    subprocess.run(
        [
            str(python_path), "-m", "uvicorn",
            "silverforge.api:app",
            "--host=0.0.0.0",
            "--port=8000",
            "--reload",
        ],
        env=env,
        cwd=PROJECT_ROOT,
    )


def main():
    python_path = get_venv_python()

    print(f"🐍 Python: {python_path}")

    if not check_dependencies(python_path):
        print("⚠️  의존성이 누락되었습니다.")
        install_dependencies()

        if not check_dependencies(python_path):
            print("❌ 의존성 설치 실패. 수동으로 설치해주세요:")
            print("   uv pip install -e .")
            sys.exit(1)

    if "--api" in sys.argv:
        print("🚀 Starting FastAPI server at http://localhost:8000")
        print("📖 API docs: http://localhost:8000/docs")
        run_api(python_path)
    else:
        print("🔥 Starting SilverForge UI at http://localhost:8502")
        run_streamlit(python_path)


if __name__ == "__main__":
    main()
