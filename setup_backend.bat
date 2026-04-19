@echo off
chcp 65001 >nul
echo ================================================
echo   RapidForce - Backend Setup
echo ================================================
echo.

:: Kiem tra Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [LOI] Khong tim thay Python. Tai tai: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python da san sang.

:: Tao venv neu chua co
if not exist "venv\" (
    echo.
    echo [1/4] Tao virtual environment...
    python -m venv venv
    echo [OK] Tao venv thanh cong.
) else (
    echo [OK] venv da ton tai, bo qua buoc tao.
)

:: Kich hoat venv
echo.
echo [2/4] Kich hoat venv...
call venv\Scripts\activate.bat

:: Nang cap pip
python -m pip install --upgrade pip --quiet

:: Cai dependencies chinh
echo.
echo [3/4] Cai dependencies (fastapi, chromadb, torch...)
echo      (Co the mat 3-5 phut, vui long cho...)
pip install fastapi "uvicorn[standard]" pydantic huggingface_hub chromadb sentence-transformers transformers torch --quiet
echo [OK] Dependencies da cai xong.

:: Cai llama-cpp-python (CPU prebuilt)
echo.
echo [4/4] Cai llama-cpp-python (C++ backend toc do cao)...
echo      (Co the mat 5-10 phut, vui long cho...)
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
if errorlevel 1 (
    echo.
    echo [CANH BAO] Cai llama-cpp-python that bai.
    echo            Chatbot van chay duoc nhung se cham hon (dung transformers fallback).
) else (
    echo [OK] llama-cpp-python da cai xong.
)

echo.
echo ================================================
echo   Setup hoan tat!
echo ================================================
echo.
echo De chay backend:
echo   venv\Scripts\activate.bat
echo   python -m qwen3
echo.
echo Server se chay tai: http://localhost:8001
echo (Lan dau chay se tu dong tai model ~1GB tu HuggingFace)
echo.
pause
