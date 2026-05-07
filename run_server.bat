@echo off
echo Starting Django development server...
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if requirements are installed
echo Checking dependencies...
pip list | findstr "Django" >nul
if errorlevel 1 (
    echo Django not found. Installing requirements...
    pip install -r requirements.txt
)

REM Run migrations
echo Running database migrations...
python manage.py migrate

REM Collect static files
echo Collecting static files...
python manage.py collectstatic --noinput

REM Start the development server
echo Starting development server on http://127.0.0.1:8000...
echo Press Ctrl+C to stop the server.
echo.
python manage.py runserver 127.0.0.1:8000

pause