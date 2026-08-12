@echo off
echo ========================================
echo   Telegram Sender Bot - Setup
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

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install requirements
echo Installing requirements...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements
    pause
    exit /b 1
)

REM Install tools requirements
echo Installing tools requirements...
pip install -r requirements-tools.txt
if errorlevel 1 (
    echo WARNING: Failed to install tools requirements (optional)
)

REM Create data directory
echo Creating data directory...
if not exist "data" mkdir data

REM Copy .env.example to .env if not exists
if not exist ".env" (
    echo.
    echo Creating .env file from template...
    copy .env.example .env
    echo.
    echo IMPORTANT: Please edit .env file with your settings:
    echo.
    echo 1. BOT_TOKEN - Get from @BotFather on Telegram
    echo 2. SUPER_ADMIN_ID - Your Telegram user ID
    echo.
    echo Opening .env file for editing...
    notepad .env
)

echo.
echo ========================================
echo   Setup completed!
echo ========================================
echo.
echo Next steps:
echo.
echo 1. Edit .env file with your bot token and admin ID
echo.
echo 2. To import contacts from Google Sheets:
echo    - Place credentials.json in this folder
echo    - Run: python tools/import_gsheets.py "YOUR_SHEET_URL"
echo.
echo 3. To start the bot:
echo    - Run: start.bat
echo.
echo ========================================
pause
