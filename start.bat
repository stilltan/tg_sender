@echo off
echo ========================================
echo   Telegram Sender Bot - Startup
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install requirements if needed
if not exist "venv\installed.flag" (
    echo Installing requirements...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install requirements
        pause
        exit /b 1
    )
    echo. > venv\installed.flag
)

REM Check if .env exists
if not exist ".env" (
    echo.
    echo WARNING: .env file not found!
    echo.
    echo Please create .env file with your settings:
    echo.
    echo BOT_TOKEN=your_bot_token_here
    echo SUPER_ADMIN_ID=your_telegram_id_here
    echo.
    echo Copy .env.example to .env and edit it:
    echo   copy .env.example .env
    echo   notepad .env
    echo.
    pause
    exit /b 1
)

echo.
echo Starting bot...
echo Press Ctrl+C to stop
echo.

python -m bot

pause
