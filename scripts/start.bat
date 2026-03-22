@echo off
chcp 65001 >nul
title Quant Trading - Full Stack

echo ========================================
echo   Quant Trading System - Quick Start
echo ========================================
echo.

:: Start backend
echo [1/2] Starting backend API (port 8000)...
cd /d D:\Finance
start "Quant-API" cmd /k "chcp 65001 >nul & title Quant API & python -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000"

:: Wait for backend to be ready
timeout /t 3 /nobreak >nul

:: Start frontend
echo [2/2] Starting frontend dev server (port 3000)...
cd /d D:\Finance\apps\web
start "Quant-Web" cmd /k "title Quant Web & bun run dev"

timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   Backend:  http://localhost:8000/docs
echo   Frontend: http://localhost:3000
echo ========================================
echo.
echo Press any key to open browser...
pause >nul
start http://localhost:3000
