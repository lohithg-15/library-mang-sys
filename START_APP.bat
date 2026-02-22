@echo off
REM Smart Book Finder - Complete Startup Script

echo.
echo ============================================================
echo           SMART BOOK FINDER - STARTUP SCRIPT
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

echo [1/4] Checking database...
cd /d "%~dp0BACKEND"
python -c "from database import get_all_books; books = get_all_books(); print(f'Database ready: {len(books)} books found')"

if errorlevel 1 (
    echo ERROR: Database check failed
    pause
    exit /b 1
)

echo.
echo [2/4] Starting BACKEND (FastAPI on port 8000)...
echo         Running: uvicorn main:app --reload
echo.
start "Smart Book Finder - BACKEND" cmd /k "cd /d %~dp0BACKEND && uvicorn main:app --reload"

REM Wait for backend to start
echo [3/4] Waiting for backend to start (10 seconds)...
timeout /t 10 /nobreak

echo.
echo [4/4] Starting FRONTEND (HTTP Server on port 5500)...
echo         Running: python -m http.server 5500
echo.
start "Smart Book Finder - FRONTEND" cmd /k "cd /d %~dp0FRONTEND && python -m http.server 5500"

echo.
echo ============================================================
echo           ✅ SMART BOOK FINDER IS STARTING
echo ============================================================
echo.
echo BACKEND:  http://127.0.0.1:8000
echo FRONTEND: http://localhost:5500
echo.
echo Opening application in browser...
timeout /t 3 /nobreak

start http://localhost:5500

echo.
echo ============================================================
echo           💡 TIPS
echo ============================================================
echo.
echo 1. Two new windows will open:
echo    - BACKEND window (Python/Uvicorn)
echo    - FRONTEND window (HTTP Server)
echo.
echo 2. Keep both windows open while using the application
echo.
echo 3. To stop:
echo    - Type Ctrl+C in both windows OR close them
echo.
echo 4. If you see "Address already in use":
echo    - Close the existing application
echo    - Or change the port number (5500 or 8000)
echo.
echo 5. The browser will open automatically
echo    If not, manually open: http://localhost:5500
echo.
echo ============================================================
echo.

pause
