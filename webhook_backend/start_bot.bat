@echo off
REM =============================================================================
REM TradingView -> Discord -> MT5 Bridge Startup Script
REM =============================================================================
REM
REM This script starts the trading bot on Windows.
REM Make sure MT5 terminal is running before starting the bot.
REM
REM Requirements:
REM   1. Python 3.8+ installed and in PATH
REM   2. Required packages installed (see requirements.txt)
REM   3. MT5 terminal running and logged in
REM   4. Discord bot token configured in trading_bot.py
REM
REM =============================================================================

echo ============================================================
echo   TradingView - Discord - MT5 Trading Bridge
echo ============================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ and add it to PATH
    pause
    exit /b 1
)

REM Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo No virtual environment found. Using system Python.
    echo TIP: Create a venv with: python -m venv venv
)

REM Change to script directory
cd /d "%~dp0"

echo.
echo Starting trading bot...
echo Press Ctrl+C to stop the bot.
echo.
echo Webhook URL: http://localhost:5000/webhook
echo Health Check: http://localhost:5000/health
echo.
echo ============================================================
echo.

REM Run the bot
python trading_bot.py

REM If bot exits, pause to see any error messages
echo.
echo Bot stopped.
pause
